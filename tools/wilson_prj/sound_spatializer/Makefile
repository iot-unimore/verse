EXTERNALS_PATH = ./externals/
#EXTERNALS_PATH = ./../../


########################### DO NOT MODIFY BELOW THIS LINE ##########################################

#### PROJECT SETTINGS ####

# YAML_CPP
YAML_CPP = $(EXTERNALS_PATH)/yaml-cpp/
YAML_CPP_HEADERS = $(YAML_CPP)/include
YAML_CPP_LIB = $(YAML_CPP)/build/libyaml-cpp.a

# 3DTune-In Audio Toolkit flags
_3DTI_PATH = $(EXTERNALS_PATH)/3dTuneIn/3dti_AudioToolkit
_3DTI_THIRD_PARTY = $(_3DTI_PATH)/3dti_ResourceManager/third_party_libraries

_3DTI_EXAMPLES_PATH = $(EXTERNALS_PATH)/3dTuneIn/3dti_AudioToolkit_Examples
_3DTI_EXAMPLES_THIRD_PARTY = $(_3DTI_EXAMPLES_PATH)/third_party_libraries

_3DTI_RESOURCE_MGR = $(_3DTI_PATH)/3dti_ResourceManager
_3DTI_TOOLKIT = $(_3DTI_PATH)/3dti_Toolkit
_3DTI_HEADERS =

# libsofa
SOFA = $(_3DTI_THIRD_PARTY)/sofacoustics/libsofa
SOFA_HEADERS = $(SOFA)/src
#SOFA_LIB_PATH = $(SOFA)/lib
#SOFA_LIB = $(SOFA_LIB_PATH)/libsofa.a
SOFA_3RD_PARTY_HEADERS = $(SOFA)/dependencies/include
#SOFA_3RD_PARTY_LIBS_PATH = $(SOFA)/dependencies/lib/linux
#NETCDF_LIB               =  $(SOFA_3RD_PARTY_LIBS_PATH)/libnetcdf.a
#NETCDF_CPP_LIB	          =  $(SOFA_3RD_PARTY_LIBS_PATH)/libnetcdf_c++4.a
#HDF5HL_LIB               =  $(SOFA_3RD_PARTY_LIBS_PATH)/libhdf5_hl.a
#HDF5_LIB                 =  $(SOFA_3RD_PARTY_LIBS_PATH)/libhdf5.a
#CURL_LIB                 =  $(SOFA_3RD_PARTY_LIBS_PATH)/libcurl.a
#Z_LIB                    =  $(SOFA_3RD_PARTY_LIBS_PATH)/libz.a
#SOFA_3RD_PARTY_LIBS      =  $(NETCDF_LIB) $(NETCDF_CPP_LIB) $(HDF5HL_LIB) $(HDF5_LIB) $(CURL_LIB) $(Z_LIB)

# Cereal
CEREAL = $(_3DTI_THIRD_PARTY)/cereal
CEREAL_HEADERS = $(CEREAL)/include

# Boost
BOOSTCB = $(_3DTI_THIRD_PARTY)/boost_circular_buffer
BOOSTCB_HEADERS = $(BOOSTCB)

# Eigen
EIGEN = $(_3DTI_THIRD_PARTY)/eigen
EIGEN_HEADERS = $(BOOSTCB)

# This accumulates all the third party libs used
# using the Other Linker Flags setting in the project itself.
OTHER_LDFLAGS = $(SOFA_3RD_PARTY_LIBS) $(SOFA_LIB) $(YAML_CPP_LIB)
HEADER_SEARCH_PATHS = $(_3DTI_HEADERS) $(_RTAUDIO_HEADERS) $(YAML_CPP_HEADERS)

# IMPORTANT: check 3dti_AudioToolkit/3dti_Toolkit/Common/Conventions.h to see
# the defines for 3D orientation and positioning

OTHER_CFLAGS = -D_3DTI_AXIS_CONVENTION_BINAURAL_TEST_APP -D_3DTI_ANGLE_CONVENTION_LISTEN -D__LINUX_PULSE__ 

# IMPORTANT: the define 3DTI_AXIS_CONVENTION_BINAURAL_TEST_APP will define also:
# #define UP_AXIS AXIS_Z                  ///< In the test app Z is the UP direction
# #define RIGHT_AXIS AXIS_MINUS_Y         ///< In the test app -Y is the RIGHT direction
# #define FORWARD_AXIS AXIS_X             ///< In the test app X is the FORWARD direction
#
# IMPORTANT: the define 3DTI_ANGLE_CONVENTION_LISTEN will define also:
# #define AZIMUTH_ZERO FORWARD_AXIS       ///< In LISTEN database, azimuth=0 is in the front
# #define AZIMUTH_MOTION ANTICLOCKWISE    ///< In LISTEN database, azimuth motion is anti-clockwise
# #define ELEVATION_ZERO FORWARD_AXIS     ///< In LISTEN database, elevation=0 is in the front
# #define ELEVATION_MOTION ANTICLOCKWISE  ///< In LISTEN database, elevation motion is anti-clockwise

# The name of the executable to be created
BIN_NAME := sspat

# Compiler used
CXX ?= g++
# Extension of source files used in the project
SRC_EXT = cpp
# Path to the source directory, relative to the makefile
SRC_PATH = ./src
# Space-separated pkg-config libraries used by this project
LIBS = netcdf-cxx4 libpulse libpulse-simple sndfile
# General compiler flags
COMPILE_FLAGS = -std=c++17 -fpermissive -lpthread 
# Additional release-specific flags
RCOMPILE_FLAGS = -DNDEBUG
# Additional debug-specific flags
DCOMPILE_FLAGS = -D DEBUG
# Add additional include paths
#INCLUDES = -I$(SRC_PATH) -I$(_3DTI_RESOURCE_MGR) -I$(_3DTI_TOOLKIT) -I$(CEREAL_HEADERS) -I$(BOOSTCB_HEADERS) $(_RTAUDIO_HEADERS) -I$(SOFA_HEADERS) -I$(SOFA_3RD_PARTY_HEADERS) -I$(EIGEN)
INCLUDES = -I$(SRC_PATH) -I$(_3DTI_RESOURCE_MGR) -I$(_3DTI_TOOLKIT) -I$(CEREAL_HEADERS) -I$(BOOSTCB_HEADERS) -I$(SOFA_HEADERS) -I$(SOFA_3RD_PARTY_HEADERS) -I$(EIGEN) -I$(YAML_CPP_HEADERS)

# General linker settings
LINK_FLAGS = $(OTHER_LDFLAGS) $(OTHER_CFLAGS)
# Additional release-specific linker settings
RLINK_FLAGS =
# Additional debug-specific linker settings
DLINK_FLAGS =
# Destination directory, like a jail or mounted system
DESTDIR =
# Install path (bin/ is appended automatically)
INSTALL_PREFIX = usr/local

_3DTI_TOOLKIT_PATH = $(_3DTI_PATH)/3dti_Toolkit
DEPENDENTSOURCEFILES = $(_3DTI_TOOLKIT_PATH)/BinauralSpatializer/*.cpp $(_3DTI_TOOLKIT_PATH)/Common/*.cpp $(_3DTI_TOOLKIT_PATH)/HAHLSimulation/*.cpp $(_3DTI_RESOURCE_MGR)/HRTF/*.cpp $(_3DTI_RESOURCE_MGR)/BRIR/*.cpp $(_3DTI_RESOURCE_MGR)/ILD/*.cpp $(SOFA_HEADERS)/SOFA*.cpp $(SOFA)/dependencies/include/*.cpp


#### END PROJECT SETTINGS ####

# Optionally you may move the section above to a separate config.mk file, and
# uncomment the line below
# include config.mk

# Generally should not need to edit below this line

# Obtains the OS type, either 'Darwin' (OS X) or 'Linux'
UNAME_S:=$(shell uname -s)

# Function used to check variables. Use on the command line:
# make print-VARNAME
# Useful for debugging and adding features
print-%: ; @echo $*=$($*)

# Shell used in this makefile
# bash is used for 'echo -en'
SHELL = /bin/bash
# Clear built-in rules
.SUFFIXES:
# Programs for installation
INSTALL = install
INSTALL_PROGRAM = $(INSTALL)
INSTALL_DATA = $(INSTALL) -m 644

# Append pkg-config specific libraries if need be
ifneq ($(LIBS),)
	COMPILE_FLAGS += $(shell pkg-config --cflags $(LIBS))
	LINK_FLAGS += $(shell pkg-config --libs $(LIBS))
endif

# Verbose option, to output compile and link commands
export V := false
export CMD_PREFIX := @
ifeq ($(V),true)
	CMD_PREFIX :=
endif

# Combine compiler and linker flags
release: export CXXFLAGS := $(CXXFLAGS) $(COMPILE_FLAGS) $(RCOMPILE_FLAGS)
release: export LDFLAGS := $(LDFLAGS) $(LINK_FLAGS) $(RLINK_FLAGS)
debug: export CXXFLAGS := $(CXXFLAGS) $(COMPILE_FLAGS) $(DCOMPILE_FLAGS)
debug: export LDFLAGS := $(LDFLAGS) $(LINK_FLAGS) $(DLINK_FLAGS)

# Build and output paths
release: export BUILD_PATH := build/release
release: export BIN_PATH := bin/release
debug: export BUILD_PATH := build/debug
debug: export BIN_PATH := bin/debug
install: export BIN_PATH := bin/release

# Find all source files in the source directory, sorted by most
# recently modified
ifeq ($(UNAME_S),Darwin)
	SOURCES = $(shell find $(SRC_PATH) -name '*.$(SRC_EXT)' | sort -k 1nr | cut -f2-)
else
	SOURCES = $(shell find $(SRC_PATH) -name '*.$(SRC_EXT)' -printf '%T@\t%p\n' \
						| sort -k 1nr | cut -f2-)
endif

# fallback in case the above fails
rwildcard = $(foreach d, $(wildcard $1*), $(call rwildcard,$d/,$2) \
						$(filter $(subst *,%,$2), $d))
ifeq ($(SOURCES),)
	SOURCES := $(call rwildcard, $(SRC_PATH), *.$(SRC_EXT))
endif

# Set the object file names, with the source directory stripped
# from the path, and the build path prepended in its place
OBJECTS = $(SOURCES:$(SRC_PATH)/%.$(SRC_EXT)=$(BUILD_PATH)/%.o)
# Set the dependency files that will be used to add header dependencies
DEPS = $(OBJECTS:.o=.d)

# Macros for timing compilation
ifeq ($(UNAME_S),Darwin)
	CUR_TIME = awk 'BEGIN{srand(); print srand()}'
	TIME_FILE = $(dir $@).$(notdir $@)_time
	START_TIME = $(CUR_TIME) > $(TIME_FILE)
	END_TIME = read st < $(TIME_FILE) ; \
		$(RM) $(TIME_FILE) ; \
		st=$$((`$(CUR_TIME)` - $$st)) ; \
		echo $$st
else
	TIME_FILE = $(dir $@).$(notdir $@)_time
	START_TIME = date '+%s' > $(TIME_FILE)
	END_TIME = read st < $(TIME_FILE) ; \
		$(RM) $(TIME_FILE) ; \
		st=$$((`date '+%s'` - $$st - 86400)) ; \
		echo `date -u -d @$$st '+%H:%M:%S'`
endif

# Version macros
# Comment/remove this section to remove versioning
#USE_VERSION := false
USE_VERSION := false

# If this isn't a git repo or the repo has no tags, git describe will return non-zero
ifeq ($(shell git describe > /dev/null 2>&1 ; echo $$?), 0)
	USE_VERSION := true
	VERSION := $(shell git describe --tags --long --dirty --always | \
		sed 's/v\([0-9]*\)\.\([0-9]*\)\.\([0-9]*\)-\?.*-\([0-9]*\)-\(.*\)/\1 \2 \3 \4 \5/g')
	VERSION_MAJOR := $(word 1, $(VERSION))
	VERSION_MINOR := $(word 2, $(VERSION))
	VERSION_PATCH := $(word 3, $(VERSION))
	VERSION_REVISION := $(word 4, $(VERSION))
	VERSION_HASH := $(word 5, $(VERSION))
	VERSION_STRING := \
		"$(VERSION_MAJOR).$(VERSION_MINOR).$(VERSION_PATCH).$(VERSION_REVISION)-$(VERSION_HASH)"
	override CXXFLAGS := $(CXXFLAGS) \
		-D VERSION_MAJOR=$(VERSION_MAJOR) \
		-D VERSION_MINOR=$(VERSION_MINOR) \
		-D VERSION_PATCH=$(VERSION_PATCH) \
		-D VERSION_REVISION=$(VERSION_REVISION) \
		-D VERSION_HASH=\"$(VERSION_HASH)\"
endif

# Standard, non-optimized release build
.PHONY: release
release: dirs
ifeq ($(USE_VERSION), true)
	@echo "Beginning release build v$(VERSION_STRING)"
else
	@echo "Beginning release build"
endif
	@$(START_TIME)
	@$(MAKE) all --no-print-directory
	@echo -n "Total build time: "
	@$(END_TIME)

# Debug build for gdb debugging
.PHONY: debug
debug: dirs
ifeq ($(USE_VERSION), true)
	@echo "Beginning debug build v$(VERSION_STRING)"
else
	@echo "Beginning debug build"
endif
	@$(START_TIME)
	@$(MAKE) all --no-print-directory
	@echo -n "Total build time: "
	@$(END_TIME)

# Create the directories used in the build
.PHONY: dirs
dirs:
	@echo "Creating directories"
	@mkdir -p $(dir $(OBJECTS))
	@mkdir -p $(BIN_PATH)

# Installs to the set path
.PHONY: install
install:
	@echo "Installing to $(DESTDIR)$(INSTALL_PREFIX)/bin"
	@$(INSTALL_PROGRAM) $(BIN_PATH)/$(BIN_NAME) $(DESTDIR)$(INSTALL_PREFIX)/bin

# Uninstalls the program
.PHONY: uninstall
uninstall:
	@echo "Removing $(DESTDIR)$(INSTALL_PREFIX)/bin/$(BIN_NAME)"
	@$(RM) $(DESTDIR)$(INSTALL_PREFIX)/bin/$(BIN_NAME)

# Removes all build files
.PHONY: clean
clean:
	@echo "Deleting $(BIN_NAME) symlink"
	@$(RM) $(BIN_NAME)
	@echo "Deleting directories"
	@$(RM) -r build
	@$(RM) -r bin

# Main rule, checks the executable and symlinks to the output
all: $(BIN_PATH)/$(BIN_NAME)
	@echo "Making symlink: $(BIN_NAME) -> $<"
	@$(RM) $(BIN_NAME)
	@ln -s $(BIN_PATH)/$(BIN_NAME) $(BIN_NAME)

# Link the executable
$(BIN_PATH)/$(BIN_NAME): $(OBJECTS)
	@echo "Linking: $@"
	@$(START_TIME)
	$(CMD_PREFIX)$(CXX) -pthread $(CXXFLAGS) $(DEPENDENTSOURCEFILES) $(INCLUDES) $(OBJECTS) $(LDFLAGS) -o $@
	@echo -en "\t Link time: "
	@$(END_TIME)

# Add dependency files, if they exist
-include $(DEPS)

# Source file rules
# After the first compilation they will be joined with the rules from the
# dependency files to provide header dependencies
$(BUILD_PATH)/%.o: $(SRC_PATH)/%.$(SRC_EXT)
	@echo "Compiling: $< -> $@"
	@$(START_TIME)
	$(CMD_PREFIX)$(CXX) -pthread $(CXXFLAGS) $(INCLUDES) -MP -MMD -c $< -o $@
	@echo -en "\t Compile time: "
	@$(END_TIME)
