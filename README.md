# RunAI Job monitoring Readme

## Overview

The monitoring script is a Python application designed to monitor the speed and status of specified jobs running on remote servers. It uses the RunAI command-line tool to gather job details and displays relevant information in a graphical user interface (GUI) built using the Tkinter library.

## Features

- **Job Speed Monitoring:** Monitors the speed of specified jobs by retrieving details such as the mean and latest iteration speed.
  
- **Job Status Indication:** Displays the status of each job based on its speed compared to historical averages. Different status levels are color-coded for easy identification.

- **Node Information:** Provides an overview of the average speed for each unique node where jobs are executed.

## Dependencies

- **Python:** The script is written in Python and requires a Python interpreter (3.6 or later).

- **Tkinter:** Used for creating the GUI.

- **NumPy:** Utilized for numerical operations, particularly in calculating the mean speed.

## Usage

### Command Line Arguments

The script accepts the following command-line arguments:

- `--username`: RunAI username.

- `--server_address`: Server address or alias. Default is set to "dgx1a".

- `--job_names`: List of job names to monitor.

- `--speed_history`: Number of iterations to average speed over. Default is set to 100.

- `--loop_timing`: How often to update the GUI in seconds. Default is set to 100 seconds.

### Running the Script

To run the script, execute it from the command line with the desired arguments. For example:

```bash
python3 monitoring.py --username your_username --job_names job1 job2 --speed_history 50 --loop_timing 60
