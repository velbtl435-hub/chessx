//! ChessX desktop: runs the PyInstaller-frozen ChessX engine (Tauri sidecar)
//! inside a pseudo-terminal and streams it to an xterm.js view.
use std::io::{Read, Write};
use std::path::PathBuf;
use std::sync::Mutex;

use portable_pty::{native_pty_system, Child, CommandBuilder, MasterPty, PtySize};
use tauri::{AppHandle, Emitter, State};

#[derive(Default)]
struct Pty {
    inner: Mutex<Option<Session>>,
}

struct Session {
    master: Box<dyn MasterPty + Send>,
    writer: Box<dyn Write + Send>,
    child: Box<dyn Child + Send + Sync>,
}

/// Tauri places `externalBin` sidecars next to the main executable (target triple stripped).
/// `CHESSX_ENGINE` overrides it (e.g. `python3 /path/chessx.py` is not supported; point to a binary).
fn engine_path() -> Result<PathBuf, String> {
    if let Ok(p) = std::env::var("CHESSX_ENGINE") {
        return Ok(PathBuf::from(p));
    }
    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let dir = exe.parent().ok_or("no exe dir")?;
    let name = if cfg!(windows) { "chessx-engine.exe" } else { "chessx-engine" };
    let p = dir.join(name);
    if p.exists() { Ok(p) } else { Err(format!("engine not found at {}", p.display())) }
}

#[tauri::command]
fn pty_start(app: AppHandle, state: State<'_, Pty>, cols: u16, rows: u16) -> Result<(), String> {
    let mut guard = state.inner.lock().unwrap();
    if let Some(s) = guard.as_mut() {
        if s.child.try_wait().ok().flatten().is_none() {
            return Ok(()); // already running (e.g. page reload)
        }
    }
    let pair = native_pty_system()
        .openpty(PtySize { rows: rows.max(5), cols: cols.max(20), pixel_width: 0, pixel_height: 0 })
        .map_err(|e| e.to_string())?;
    let mut cmd = CommandBuilder::new(engine_path()?);
    cmd.env("TERM", "xterm-256color");
    cmd.env("PYTHONUNBUFFERED", "1");
    cmd.env("PYTHONIOENCODING", "utf-8");
    if let Some(home) = dirs_home() {
        cmd.cwd(home);
    }
    let child = pair.slave.spawn_command(cmd).map_err(|e| e.to_string())?;
    drop(pair.slave);
    let mut reader = pair.master.try_clone_reader().map_err(|e| e.to_string())?;
    let writer = pair.master.take_writer().map_err(|e| e.to_string())?;

    let app2 = app.clone();
    std::thread::spawn(move || {
        let mut buf = [0u8; 8192];
        let mut pending: Vec<u8> = Vec::new();
        loop {
            match reader.read(&mut buf) {
                Ok(0) | Err(_) => break,
                Ok(n) => {
                    pending.extend_from_slice(&buf[..n]);
                    // emit only complete UTF-8; keep a trailing partial sequence for the next read
                    let cut = match std::str::from_utf8(&pending) {
                        Ok(_) => pending.len(),
                        Err(e) if e.error_len().is_none() => e.valid_up_to(),
                        Err(_) => pending.len(),
                    };
                    let chunk: Vec<u8> = pending.drain(..cut).collect();
                    let _ = app2.emit("pty-data", String::from_utf8_lossy(&chunk).to_string());
                }
            }
        }
        let _ = app2.emit("pty-exit", "eof");
    });

    *guard = Some(Session { master: pair.master, writer, child });
    Ok(())
}

fn dirs_home() -> Option<PathBuf> {
    std::env::var_os(if cfg!(windows) { "USERPROFILE" } else { "HOME" }).map(PathBuf::from)
}

#[tauri::command]
fn pty_write(state: State<'_, Pty>, data: String) -> Result<(), String> {
    if let Some(s) = state.inner.lock().unwrap().as_mut() {
        s.writer.write_all(data.as_bytes()).map_err(|e| e.to_string())?;
        s.writer.flush().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn pty_resize(state: State<'_, Pty>, cols: u16, rows: u16) -> Result<(), String> {
    if let Some(s) = state.inner.lock().unwrap().as_ref() {
        s.master
            .resize(PtySize { rows, cols, pixel_width: 0, pixel_height: 0 })
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

pub fn run() {
    tauri::Builder::default()
        .manage(Pty::default())
        .invoke_handler(tauri::generate_handler![pty_start, pty_write, pty_resize])
        .build(tauri::generate_context!())
        .expect("error while building ChessX")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                use tauri::Manager;
                if let Some(s) = app.state::<Pty>().inner.lock().unwrap().as_mut() {
                    let _ = s.child.kill();
                }
            }
        });
}
