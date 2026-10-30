# ChessX C / WASI build pipeline.
#   make              native + wasm for every module
#   make native       build/native/libcx_<mod>.so (+ <mod>_cli)
#   make wasm         build/wasm/<mod>.wasm (WASI command) + <mod>.reactor.wasm (exports only)
#   make emscripten   build/emscripten/<mod>.js/.wasm (optional; needs emcc)
#   make test         build everything and run native / wasm / Python parity tests
#   make size         size report (+ wasm-opt -Oz if installed)
#   make clean
# A module is any c/<dir>/ containing src/*.c (dirs without sources are skipped).

WASI_SDK ?= /opt/wasi-sdk
WASI_TARGET ?= wasm32-wasip1
CC ?= cc
WASM_CC ?= $(WASI_SDK)/bin/clang
EMCC ?= emcc
WASMTIME ?= wasmtime
PYTHON ?= python3

UNAME_S := $(shell uname -s 2>/dev/null)
ifeq ($(OS),Windows_NT)
  SOEXT := dll
else ifeq ($(UNAME_S),Darwin)
  SOEXT := dylib
else
  SOEXT := so
endif

CFLAGS ?= -O2
CFLAGS += -std=c99 -Wall -Wextra -Werror -Iinclude
NATIVE_FLAGS := -fPIC -fvisibility=hidden
WASM_FLAGS := --target=$(WASI_TARGET) --sysroot=$(WASI_SDK)/share/wasi-sysroot

B := build
MODULES := $(patsubst %/,%,$(dir $(patsubst %/src/,%/,$(dir $(wildcard */src/*.c)))))
MODULES := $(sort $(MODULES))
COMMON := $(wildcard common/*.c)
src_of = $(wildcard $(1)/src/*.c) $(COMMON)

NATIVE_LIBS := $(foreach m,$(MODULES),$(B)/native/libcx_$(m).$(SOEXT))
NATIVE_CLIS := $(foreach m,$(MODULES),$(if $(wildcard $(m)/cli.c),$(B)/native/$(m)_cli))
WASM_CMDS := $(foreach m,$(MODULES),$(if $(wildcard $(m)/cli.c),$(B)/wasm/$(m).wasm))
WASM_REACTORS := $(foreach m,$(MODULES),$(B)/wasm/$(m).reactor.wasm)

.PHONY: all native wasm emscripten test size clean list
all: native wasm
list:
	@echo "modules: $(MODULES)"
native: $(NATIVE_LIBS) $(NATIVE_CLIS)
wasm: $(WASM_CMDS) $(WASM_REACTORS)

.SECONDEXPANSION:
$(B)/native/libcx_%.$(SOEXT): $$(call src_of,%) $$(wildcard %/*.h) $(wildcard include/*.h)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(NATIVE_FLAGS) -shared -o $@ $(call src_of,$*)

$(B)/native/%_cli: %/cli.c $$(call src_of,%) $$(wildcard %/*.h)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -o $@ $< $(call src_of,$*)

$(B)/wasm/%.wasm: %/cli.c $$(call src_of,%) $$(wildcard %/*.h)
	@mkdir -p $(@D)
	$(WASM_CC) $(WASM_FLAGS) $(CFLAGS) -o $@ $< $(call src_of,$*)

$(B)/wasm/%.reactor.wasm: $$(call src_of,%) $$(wildcard %/*.h)
	@mkdir -p $(@D)
	$(WASM_CC) $(WASM_FLAGS) $(CFLAGS) -mexec-model=reactor -o $@ $(call src_of,$*)

emscripten:
	@command -v $(EMCC) >/dev/null || { echo "emcc not found: install emsdk (see c/README.md)"; exit 1; }
	@mkdir -p $(B)/emscripten
	@for m in $(MODULES); do \
	  echo "$(EMCC) $$m"; \
	  $(EMCC) $(CFLAGS) -sMODULARIZE -sEXPORT_NAME=cx_$$m -sEXPORTED_RUNTIME_METHODS=ccall,cwrap \
	    -sEXPORTED_FUNCTIONS=_malloc,_free -o $(B)/emscripten/$$m.js $(call src_of,$$m) || exit 1; \
	done

test: all
	$(PYTHON) tests/run_parity.py --build $(B) --wasmtime $(WASMTIME)

size: wasm
	@for f in $(B)/wasm/*.wasm; do \
	  printf "%-40s %8s bytes" $$f $$(wc -c < $$f); \
	  if command -v wasm-opt >/dev/null; then wasm-opt -Oz $$f -o $$f.opt && printf "  -Oz %8s" $$(wc -c < $$f.opt) && rm $$f.opt; fi; \
	  echo; done

clean:
	rm -rf $(B)
