# c/capstone/module.mk — extra build rules for the vendored capstone engine.
# Needs ONE line in c/Makefile (after the variable block):   -include */module.mk
# Until then the Makefile builds the stub (cx_cs_available()==0). Test locally with:
#   make -C c -f Makefile -f capstone/module.mk all test
CS_V := capstone/vendor
CS_ARCHS := X86 ARM AArch64 Mips RISCV
CS_SRCS := $(addprefix $(CS_V)/,cs.c MCInst.c MCInstrDesc.c MCRegisterInfo.c SStream.c Mapping.c utils.c) \
           $(foreach a,$(CS_ARCHS),$(wildcard $(CS_V)/arch/$(a)/*.c))
CS_DEFS := -DCX_CAPSTONE_VENDOR -DCAPSTONE_USE_SYS_DYN_MEM -DCAPSTONE_HAS_X86 -DCAPSTONE_HAS_ARM \
           -DCAPSTONE_HAS_ARM64 -DCAPSTONE_HAS_MIPS -DCAPSTONE_HAS_RISCV
# capstone is third-party: no -Werror/-std=c99 for it (vendor code is gnu99 and warns a lot)
CS_CFLAGS := -O2 -std=gnu99 -w -Iinclude -I$(CS_V)/include $(CS_DEFS)

_cx_src_of_base := $(value src_of)
src_of = $(wildcard $(1)/src/*.c) $(COMMON) $(if $(filter capstone,$(1)),$(CS_SRCS))

$(B)/native/libcx_capstone.$(SOEXT) $(B)/native/capstone_cli $(B)/wasm/capstone.wasm $(B)/wasm/capstone.reactor.wasm: CFLAGS := $(CS_CFLAGS)
$(B)/native/libcx_capstone.$(SOEXT) $(B)/native/capstone_cli $(B)/wasm/capstone.wasm $(B)/wasm/capstone.reactor.wasm: $(CS_SRCS)
