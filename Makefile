WORK_DIR = $(shell pwd)
PDK ?= ihp-sg13g2

IHP_SG13G2_PDK_REPO = https://github.com/IHP-GmbH/IHP-Open-PDK.git
IHP_SG13G2_PDK_BRANCH = dev
IHP_SG13G2_PDK_COMMIT = af19e4730ee600ec98c36ccf0a1b38abd780b686

IHP_SG13CMOS5L_PDK_REPO = https://github.com/IHP-GmbH/ihp-sg13cmos5l.git
IHP_SG13CMOS5L_PDK_BRANCH = main
IHP_SG13CMOS5L_PDK_COMMIT = e8a87d708b8977e7c07684b033658a0f80af59a0

ifeq ($(PDK),ihp-sg13g2)
CLONE_TARGET := clone-ihp-sg13g2-pdk
else ifeq ($(PDK),ihp-sg13cmos5l)
CLONE_TARGET := clone-ihp-sg13cmos5l-pdk
else
CLONE_TARGET := unsupported-pdk
endif

.PHONY: clone-pdk
clone-pdk: $(CLONE_TARGET)

.PHONY: clone-ihp-sg13g2-pdk
clone-ihp-sg13g2-pdk:
	git clone -b $(IHP_SG13G2_PDK_BRANCH) $(IHP_SG13G2_PDK_REPO) pdk
	git -C pdk checkout $(IHP_SG13G2_PDK_COMMIT)

.PHONY: clone-ihp-sg13cmos5l-pdk
clone-ihp-sg13cmos5l-pdk: clone-ihp-sg13g2-pdk
	git -C pdk clone -b $(IHP_SG13CMOS5L_PDK_BRANCH) $(IHP_SG13CMOS5L_PDK_REPO)
	git -C pdk/ihp-sg13cmos5l checkout $(IHP_SG13CMOS5L_PDK_COMMIT)

.PHONY: clean
clean:
	rm -rf pdk
