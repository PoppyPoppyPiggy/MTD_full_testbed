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

# Utility rule file for sphinx_models.

# Include any custom commands dependencies for this target.
include CMakeFiles/sphinx_models.dir/compiler_depend.make

# Include the progress variables for this target.
include CMakeFiles/sphinx_models.dir/progress.make

CMakeFiles/sphinx_models:
	echo The following Sphinx dependencies are missing: Sphinx epstopdf latexmk dvipng dia. Reconfigure the project after installing them.

CMakeFiles/sphinx_models.dir/codegen:
.PHONY : CMakeFiles/sphinx_models.dir/codegen

sphinx_models: CMakeFiles/sphinx_models
sphinx_models: CMakeFiles/sphinx_models.dir/build.make
.PHONY : sphinx_models

# Rule to build all files generated by this target.
CMakeFiles/sphinx_models.dir/build: sphinx_models
.PHONY : CMakeFiles/sphinx_models.dir/build

CMakeFiles/sphinx_models.dir/clean:
	$(CMAKE_COMMAND) -P CMakeFiles/sphinx_models.dir/cmake_clean.cmake
.PHONY : CMakeFiles/sphinx_models.dir/clean

CMakeFiles/sphinx_models.dir/depend:
	cd /home/kali/MTD/ns-3.45/cmake-cache && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/kali/MTD/ns-3.45 /home/kali/MTD/ns-3.45 /home/kali/MTD/ns-3.45/cmake-cache /home/kali/MTD/ns-3.45/cmake-cache /home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles/sphinx_models.dir/DependInfo.cmake "--color=$(COLOR)"
.PHONY : CMakeFiles/sphinx_models.dir/depend

