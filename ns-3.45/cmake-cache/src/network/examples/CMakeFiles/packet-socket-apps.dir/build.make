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
include src/network/examples/CMakeFiles/packet-socket-apps.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include src/network/examples/CMakeFiles/packet-socket-apps.dir/compiler_depend.make

# Include the progress variables for this target.
include src/network/examples/CMakeFiles/packet-socket-apps.dir/progress.make

# Include the compile flags for this target's objects.
include src/network/examples/CMakeFiles/packet-socket-apps.dir/flags.make

src/network/examples/CMakeFiles/packet-socket-apps.dir/codegen:
.PHONY : src/network/examples/CMakeFiles/packet-socket-apps.dir/codegen

src/network/examples/CMakeFiles/packet-socket-apps.dir/packet-socket-apps.cc.o: src/network/examples/CMakeFiles/packet-socket-apps.dir/flags.make
src/network/examples/CMakeFiles/packet-socket-apps.dir/packet-socket-apps.cc.o: /home/kali/MTD/ns-3.45/src/network/examples/packet-socket-apps.cc
src/network/examples/CMakeFiles/packet-socket-apps.dir/packet-socket-apps.cc.o: src/network/examples/CMakeFiles/packet-socket-apps.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building CXX object src/network/examples/CMakeFiles/packet-socket-apps.dir/packet-socket-apps.cc.o"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/network/examples && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -MD -MT src/network/examples/CMakeFiles/packet-socket-apps.dir/packet-socket-apps.cc.o -MF CMakeFiles/packet-socket-apps.dir/packet-socket-apps.cc.o.d -o CMakeFiles/packet-socket-apps.dir/packet-socket-apps.cc.o -c /home/kali/MTD/ns-3.45/src/network/examples/packet-socket-apps.cc

src/network/examples/CMakeFiles/packet-socket-apps.dir/packet-socket-apps.cc.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Preprocessing CXX source to CMakeFiles/packet-socket-apps.dir/packet-socket-apps.cc.i"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/network/examples && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -E /home/kali/MTD/ns-3.45/src/network/examples/packet-socket-apps.cc > CMakeFiles/packet-socket-apps.dir/packet-socket-apps.cc.i

src/network/examples/CMakeFiles/packet-socket-apps.dir/packet-socket-apps.cc.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Compiling CXX source to assembly CMakeFiles/packet-socket-apps.dir/packet-socket-apps.cc.s"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/network/examples && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -S /home/kali/MTD/ns-3.45/src/network/examples/packet-socket-apps.cc -o CMakeFiles/packet-socket-apps.dir/packet-socket-apps.cc.s

# Object files for target packet-socket-apps
packet__socket__apps_OBJECTS = \
"CMakeFiles/packet-socket-apps.dir/packet-socket-apps.cc.o"

# External object files for target packet-socket-apps
packet__socket__apps_EXTERNAL_OBJECTS =

/home/kali/MTD/ns-3.45/build/src/network/examples/ns3.45-packet-socket-apps-default: src/network/examples/CMakeFiles/packet-socket-apps.dir/packet-socket-apps.cc.o
/home/kali/MTD/ns-3.45/build/src/network/examples/ns3.45-packet-socket-apps-default: src/network/examples/CMakeFiles/packet-socket-apps.dir/build.make
/home/kali/MTD/ns-3.45/build/src/network/examples/ns3.45-packet-socket-apps-default: /usr/lib/x86_64-linux-gnu/libgsl.so
/home/kali/MTD/ns-3.45/build/src/network/examples/ns3.45-packet-socket-apps-default: /usr/lib/x86_64-linux-gnu/libgslcblas.so
/home/kali/MTD/ns-3.45/build/src/network/examples/ns3.45-packet-socket-apps-default: src/network/examples/CMakeFiles/packet-socket-apps.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --bold --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX executable /home/kali/MTD/ns-3.45/build/src/network/examples/ns3.45-packet-socket-apps-default"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/network/examples && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/packet-socket-apps.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
src/network/examples/CMakeFiles/packet-socket-apps.dir/build: /home/kali/MTD/ns-3.45/build/src/network/examples/ns3.45-packet-socket-apps-default
.PHONY : src/network/examples/CMakeFiles/packet-socket-apps.dir/build

src/network/examples/CMakeFiles/packet-socket-apps.dir/clean:
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/network/examples && $(CMAKE_COMMAND) -P CMakeFiles/packet-socket-apps.dir/cmake_clean.cmake
.PHONY : src/network/examples/CMakeFiles/packet-socket-apps.dir/clean

src/network/examples/CMakeFiles/packet-socket-apps.dir/depend:
	cd /home/kali/MTD/ns-3.45/cmake-cache && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/kali/MTD/ns-3.45 /home/kali/MTD/ns-3.45/src/network/examples /home/kali/MTD/ns-3.45/cmake-cache /home/kali/MTD/ns-3.45/cmake-cache/src/network/examples /home/kali/MTD/ns-3.45/cmake-cache/src/network/examples/CMakeFiles/packet-socket-apps.dir/DependInfo.cmake "--color=$(COLOR)"
.PHONY : src/network/examples/CMakeFiles/packet-socket-apps.dir/depend

