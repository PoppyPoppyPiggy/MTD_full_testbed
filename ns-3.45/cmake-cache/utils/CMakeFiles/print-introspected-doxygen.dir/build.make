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
include utils/CMakeFiles/print-introspected-doxygen.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include utils/CMakeFiles/print-introspected-doxygen.dir/compiler_depend.make

# Include the progress variables for this target.
include utils/CMakeFiles/print-introspected-doxygen.dir/progress.make

# Include the compile flags for this target's objects.
include utils/CMakeFiles/print-introspected-doxygen.dir/flags.make

utils/CMakeFiles/print-introspected-doxygen.dir/codegen:
.PHONY : utils/CMakeFiles/print-introspected-doxygen.dir/codegen

utils/CMakeFiles/print-introspected-doxygen.dir/print-introspected-doxygen.cc.o: utils/CMakeFiles/print-introspected-doxygen.dir/flags.make
utils/CMakeFiles/print-introspected-doxygen.dir/print-introspected-doxygen.cc.o: /home/kali/MTD/ns-3.45/utils/print-introspected-doxygen.cc
utils/CMakeFiles/print-introspected-doxygen.dir/print-introspected-doxygen.cc.o: utils/CMakeFiles/print-introspected-doxygen.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building CXX object utils/CMakeFiles/print-introspected-doxygen.dir/print-introspected-doxygen.cc.o"
	cd /home/kali/MTD/ns-3.45/cmake-cache/utils && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -MD -MT utils/CMakeFiles/print-introspected-doxygen.dir/print-introspected-doxygen.cc.o -MF CMakeFiles/print-introspected-doxygen.dir/print-introspected-doxygen.cc.o.d -o CMakeFiles/print-introspected-doxygen.dir/print-introspected-doxygen.cc.o -c /home/kali/MTD/ns-3.45/utils/print-introspected-doxygen.cc

utils/CMakeFiles/print-introspected-doxygen.dir/print-introspected-doxygen.cc.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Preprocessing CXX source to CMakeFiles/print-introspected-doxygen.dir/print-introspected-doxygen.cc.i"
	cd /home/kali/MTD/ns-3.45/cmake-cache/utils && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -E /home/kali/MTD/ns-3.45/utils/print-introspected-doxygen.cc > CMakeFiles/print-introspected-doxygen.dir/print-introspected-doxygen.cc.i

utils/CMakeFiles/print-introspected-doxygen.dir/print-introspected-doxygen.cc.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Compiling CXX source to assembly CMakeFiles/print-introspected-doxygen.dir/print-introspected-doxygen.cc.s"
	cd /home/kali/MTD/ns-3.45/cmake-cache/utils && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -S /home/kali/MTD/ns-3.45/utils/print-introspected-doxygen.cc -o CMakeFiles/print-introspected-doxygen.dir/print-introspected-doxygen.cc.s

# Object files for target print-introspected-doxygen
print__introspected__doxygen_OBJECTS = \
"CMakeFiles/print-introspected-doxygen.dir/print-introspected-doxygen.cc.o"

# External object files for target print-introspected-doxygen
print__introspected__doxygen_EXTERNAL_OBJECTS =

/home/kali/MTD/ns-3.45/build/utils/ns3.45-print-introspected-doxygen-default: utils/CMakeFiles/print-introspected-doxygen.dir/print-introspected-doxygen.cc.o
/home/kali/MTD/ns-3.45/build/utils/ns3.45-print-introspected-doxygen-default: utils/CMakeFiles/print-introspected-doxygen.dir/build.make
/home/kali/MTD/ns-3.45/build/utils/ns3.45-print-introspected-doxygen-default: /usr/lib/x86_64-linux-gnu/libxml2.so
/home/kali/MTD/ns-3.45/build/utils/ns3.45-print-introspected-doxygen-default: /usr/lib/x86_64-linux-gnu/libgsl.so
/home/kali/MTD/ns-3.45/build/utils/ns3.45-print-introspected-doxygen-default: /usr/lib/x86_64-linux-gnu/libgslcblas.so
/home/kali/MTD/ns-3.45/build/utils/ns3.45-print-introspected-doxygen-default: utils/CMakeFiles/print-introspected-doxygen.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --bold --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX executable /home/kali/MTD/ns-3.45/build/utils/ns3.45-print-introspected-doxygen-default"
	cd /home/kali/MTD/ns-3.45/cmake-cache/utils && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/print-introspected-doxygen.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
utils/CMakeFiles/print-introspected-doxygen.dir/build: /home/kali/MTD/ns-3.45/build/utils/ns3.45-print-introspected-doxygen-default
.PHONY : utils/CMakeFiles/print-introspected-doxygen.dir/build

utils/CMakeFiles/print-introspected-doxygen.dir/clean:
	cd /home/kali/MTD/ns-3.45/cmake-cache/utils && $(CMAKE_COMMAND) -P CMakeFiles/print-introspected-doxygen.dir/cmake_clean.cmake
.PHONY : utils/CMakeFiles/print-introspected-doxygen.dir/clean

utils/CMakeFiles/print-introspected-doxygen.dir/depend:
	cd /home/kali/MTD/ns-3.45/cmake-cache && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/kali/MTD/ns-3.45 /home/kali/MTD/ns-3.45/utils /home/kali/MTD/ns-3.45/cmake-cache /home/kali/MTD/ns-3.45/cmake-cache/utils /home/kali/MTD/ns-3.45/cmake-cache/utils/CMakeFiles/print-introspected-doxygen.dir/DependInfo.cmake "--color=$(COLOR)"
.PHONY : utils/CMakeFiles/print-introspected-doxygen.dir/depend

