# CMAKE generated file: DO NOT EDIT!
# Generated by "Unix Makefiles" Generator, CMake Version 3.31

# Delete rule output on recipe failure.
.DELETE_ON_ERROR:

#=============================================================================
# Special targets provided by cmake.

# Disable implicit rules so canonical targets will work.
.SUFFIXES:

# Disable VCS-based implicit rules.
% : %,v

# Disable VCS-based implicit rules.
% : RCS/%

# Disable VCS-based implicit rules.
% : RCS/%,v

# Disable VCS-based implicit rules.
% : SCCS/s.%

# Disable VCS-based implicit rules.
% : s.%

.SUFFIXES: .hpux_make_needs_suffix_list

# Command-line flag to silence nested $(MAKE).
$(VERBOSE)MAKESILENT = -s

#Suppress display of executed commands.
$(VERBOSE).SILENT:

# A target that is always out of date.
cmake_force:
.PHONY : cmake_force

#=============================================================================
# Set environment variables for the build.

# The shell in which to execute make rules.
SHELL = /bin/sh

# The CMake executable.
CMAKE_COMMAND = /usr/bin/cmake

# The command to remove a file.
RM = /usr/bin/cmake -E rm -f

# Escaping for special characters.
EQUALS = =

# The top-level source directory on which CMake was run.
CMAKE_SOURCE_DIR = /home/kali/MTD/ns-3.45

# The top-level build directory on which CMake was run.
CMAKE_BINARY_DIR = /home/kali/MTD/ns-3.45/cmake-cache

# Include any dependencies generated for this target.
include src/tap-bridge/CMakeFiles/tap-bridge.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include src/tap-bridge/CMakeFiles/tap-bridge.dir/compiler_depend.make

# Include the progress variables for this target.
include src/tap-bridge/CMakeFiles/tap-bridge.dir/progress.make

# Include the compile flags for this target's objects.
include src/tap-bridge/CMakeFiles/tap-bridge.dir/flags.make

src/tap-bridge/CMakeFiles/tap-bridge.dir/codegen:
.PHONY : src/tap-bridge/CMakeFiles/tap-bridge.dir/codegen

src/tap-bridge/CMakeFiles/tap-bridge.dir/helper/tap-bridge-helper.cc.o: src/tap-bridge/CMakeFiles/tap-bridge.dir/flags.make
src/tap-bridge/CMakeFiles/tap-bridge.dir/helper/tap-bridge-helper.cc.o: /home/kali/MTD/ns-3.45/src/tap-bridge/helper/tap-bridge-helper.cc
src/tap-bridge/CMakeFiles/tap-bridge.dir/helper/tap-bridge-helper.cc.o: src/tap-bridge/CMakeFiles/tap-bridge.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building CXX object src/tap-bridge/CMakeFiles/tap-bridge.dir/helper/tap-bridge-helper.cc.o"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/tap-bridge && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -MD -MT src/tap-bridge/CMakeFiles/tap-bridge.dir/helper/tap-bridge-helper.cc.o -MF CMakeFiles/tap-bridge.dir/helper/tap-bridge-helper.cc.o.d -o CMakeFiles/tap-bridge.dir/helper/tap-bridge-helper.cc.o -c /home/kali/MTD/ns-3.45/src/tap-bridge/helper/tap-bridge-helper.cc

src/tap-bridge/CMakeFiles/tap-bridge.dir/helper/tap-bridge-helper.cc.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Preprocessing CXX source to CMakeFiles/tap-bridge.dir/helper/tap-bridge-helper.cc.i"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/tap-bridge && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -E /home/kali/MTD/ns-3.45/src/tap-bridge/helper/tap-bridge-helper.cc > CMakeFiles/tap-bridge.dir/helper/tap-bridge-helper.cc.i

src/tap-bridge/CMakeFiles/tap-bridge.dir/helper/tap-bridge-helper.cc.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Compiling CXX source to assembly CMakeFiles/tap-bridge.dir/helper/tap-bridge-helper.cc.s"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/tap-bridge && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -S /home/kali/MTD/ns-3.45/src/tap-bridge/helper/tap-bridge-helper.cc -o CMakeFiles/tap-bridge.dir/helper/tap-bridge-helper.cc.s

src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-bridge.cc.o: src/tap-bridge/CMakeFiles/tap-bridge.dir/flags.make
src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-bridge.cc.o: /home/kali/MTD/ns-3.45/src/tap-bridge/model/tap-bridge.cc
src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-bridge.cc.o: src/tap-bridge/CMakeFiles/tap-bridge.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Building CXX object src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-bridge.cc.o"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/tap-bridge && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -MD -MT src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-bridge.cc.o -MF CMakeFiles/tap-bridge.dir/model/tap-bridge.cc.o.d -o CMakeFiles/tap-bridge.dir/model/tap-bridge.cc.o -c /home/kali/MTD/ns-3.45/src/tap-bridge/model/tap-bridge.cc

src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-bridge.cc.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Preprocessing CXX source to CMakeFiles/tap-bridge.dir/model/tap-bridge.cc.i"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/tap-bridge && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -E /home/kali/MTD/ns-3.45/src/tap-bridge/model/tap-bridge.cc > CMakeFiles/tap-bridge.dir/model/tap-bridge.cc.i

src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-bridge.cc.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Compiling CXX source to assembly CMakeFiles/tap-bridge.dir/model/tap-bridge.cc.s"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/tap-bridge && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -S /home/kali/MTD/ns-3.45/src/tap-bridge/model/tap-bridge.cc -o CMakeFiles/tap-bridge.dir/model/tap-bridge.cc.s

src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-encode-decode.cc.o: src/tap-bridge/CMakeFiles/tap-bridge.dir/flags.make
src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-encode-decode.cc.o: /home/kali/MTD/ns-3.45/src/tap-bridge/model/tap-encode-decode.cc
src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-encode-decode.cc.o: src/tap-bridge/CMakeFiles/tap-bridge.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_3) "Building CXX object src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-encode-decode.cc.o"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/tap-bridge && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -MD -MT src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-encode-decode.cc.o -MF CMakeFiles/tap-bridge.dir/model/tap-encode-decode.cc.o.d -o CMakeFiles/tap-bridge.dir/model/tap-encode-decode.cc.o -c /home/kali/MTD/ns-3.45/src/tap-bridge/model/tap-encode-decode.cc

src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-encode-decode.cc.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Preprocessing CXX source to CMakeFiles/tap-bridge.dir/model/tap-encode-decode.cc.i"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/tap-bridge && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -E /home/kali/MTD/ns-3.45/src/tap-bridge/model/tap-encode-decode.cc > CMakeFiles/tap-bridge.dir/model/tap-encode-decode.cc.i

src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-encode-decode.cc.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Compiling CXX source to assembly CMakeFiles/tap-bridge.dir/model/tap-encode-decode.cc.s"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/tap-bridge && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -S /home/kali/MTD/ns-3.45/src/tap-bridge/model/tap-encode-decode.cc -o CMakeFiles/tap-bridge.dir/model/tap-encode-decode.cc.s

# Object files for target tap-bridge
tap__bridge_OBJECTS = \
"CMakeFiles/tap-bridge.dir/helper/tap-bridge-helper.cc.o" \
"CMakeFiles/tap-bridge.dir/model/tap-bridge.cc.o" \
"CMakeFiles/tap-bridge.dir/model/tap-encode-decode.cc.o"

# External object files for target tap-bridge
tap__bridge_EXTERNAL_OBJECTS =

/home/kali/MTD/ns-3.45/build/lib/libns3.45-tap-bridge-default.so: src/tap-bridge/CMakeFiles/tap-bridge.dir/helper/tap-bridge-helper.cc.o
/home/kali/MTD/ns-3.45/build/lib/libns3.45-tap-bridge-default.so: src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-bridge.cc.o
/home/kali/MTD/ns-3.45/build/lib/libns3.45-tap-bridge-default.so: src/tap-bridge/CMakeFiles/tap-bridge.dir/model/tap-encode-decode.cc.o
/home/kali/MTD/ns-3.45/build/lib/libns3.45-tap-bridge-default.so: src/tap-bridge/CMakeFiles/tap-bridge.dir/build.make
/home/kali/MTD/ns-3.45/build/lib/libns3.45-tap-bridge-default.so: /usr/lib/x86_64-linux-gnu/libgsl.so
/home/kali/MTD/ns-3.45/build/lib/libns3.45-tap-bridge-default.so: /usr/lib/x86_64-linux-gnu/libgslcblas.so
/home/kali/MTD/ns-3.45/build/lib/libns3.45-tap-bridge-default.so: src/tap-bridge/CMakeFiles/tap-bridge.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --bold --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_4) "Linking CXX shared library /home/kali/MTD/ns-3.45/build/lib/libns3.45-tap-bridge-default.so"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/tap-bridge && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/tap-bridge.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
src/tap-bridge/CMakeFiles/tap-bridge.dir/build: /home/kali/MTD/ns-3.45/build/lib/libns3.45-tap-bridge-default.so
.PHONY : src/tap-bridge/CMakeFiles/tap-bridge.dir/build

src/tap-bridge/CMakeFiles/tap-bridge.dir/clean:
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/tap-bridge && $(CMAKE_COMMAND) -P CMakeFiles/tap-bridge.dir/cmake_clean.cmake
.PHONY : src/tap-bridge/CMakeFiles/tap-bridge.dir/clean

src/tap-bridge/CMakeFiles/tap-bridge.dir/depend:
	cd /home/kali/MTD/ns-3.45/cmake-cache && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/kali/MTD/ns-3.45 /home/kali/MTD/ns-3.45/src/tap-bridge /home/kali/MTD/ns-3.45/cmake-cache /home/kali/MTD/ns-3.45/cmake-cache/src/tap-bridge /home/kali/MTD/ns-3.45/cmake-cache/src/tap-bridge/CMakeFiles/tap-bridge.dir/DependInfo.cmake "--color=$(COLOR)"
.PHONY : src/tap-bridge/CMakeFiles/tap-bridge.dir/depend

