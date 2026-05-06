## Heart Rate Capture Via Bluetooth

This package contains the ROS node used by the portable study runner to read a
Polar heart-rate sensor over Bluetooth.

## Active Script

```sh
rosrun ros_bluetooth ros_bluetooth.py
```

`ros_bluetooth.py` connects to the configured Polar sensor, reads heart-rate
updates, and publishes them for the exercise coach ROS flow.

## Dependencies

- ROS Noetic.
- Python Bluetooth dependencies required by `ros_bluetooth.py`.
- A paired or reachable Polar heart-rate sensor.

The top-level portable study scripts set up the ROS workspace symlink for this
package. Start from `README_PORTABLE_STUDY.md` in the repository root when
running the full study.
