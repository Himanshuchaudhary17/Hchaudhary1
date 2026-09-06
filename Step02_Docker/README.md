# Lab 02 - Running a Linux Container with Docker

## Docker Image vs Docker Container

A Docker image is a read-only template that contains the operating system files, software, libraries, and configuration needed to create a container. An image can be reused to create multiple containers.

A Docker container is a running or stopped instance created from a Docker image. It provides an isolated environment where applications and commands can run without directly changing the host operating system.

In this lab, ‘ubuntu:22.04’ was the Docker image, while ‘my-ubuntu’ was the container created from that image. The Ubuntu image remained available even after the container was stopped or removed.
