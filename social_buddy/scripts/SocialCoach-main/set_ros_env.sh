#!/bin/bash
# save as set_ros_env.sh

# Get current IP (excluding 127.0.0.1)
IP=$(hostname -I | awk '{print $1}')

echo "Current host IP: $IP"

export ROS_MASTER_URI=http://$IP:11311
export ROS_IP=$IP

echo "ROS_MASTER_URI set to $ROS_MASTER_URI"
echo "ROS_IP set to $ROS_IP"
