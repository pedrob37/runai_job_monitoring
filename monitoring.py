import re
import subprocess
import time
import tkinter as tk
from tkinter import ttk
import numpy as np


class SpeedGUI(object):
    def __init__(self, username, server_address, job_names,
                 speed_history=100, loop_timing=10000, logging_mode="s/it"):
        self.username = username
        self.server_address = server_address
        self.job_names = job_names
        self.speed_history = speed_history
        self.loop_timing = loop_timing
        self.logging_mode = logging_mode
        self.current_time = time.time()

        self.node_dict = {}

        self.root = tk.Tk()
        self.root.title("Marshall Monitor" if username == "pedro" else "DGX Monitor")
        self.root.attributes("-topmost", True)

        self.style = ttk.Style()
        self.style.configure("BW.TLabel", background="white")
        self.style.configure("FR.TLabel", foreground="red")
        self.style.configure("FO.TLabel", foreground="dark orange")
        self.style.configure("FG.TLabel", foreground="green")
        self.style.configure("FB.TLabel", foreground="blue")
        self.style.configure("FP.TLabel", foreground="purple")

        # Separate frame for nodes
        self.job_frames = []
        self.node_frame = ttk.Frame(self.root)
        self.node_frame.pack()

        # Account for wildcards and missing job names
        if not self.job_names:
            self.fetch_job_names(wildcard=False)
        elif "*" in self.job_names[0]:
            assert len(self.job_names) == 1, "Only one wildcard supported!"
            self.fetch_job_names(wildcard=True)

        # Starting times
        self.current_times = {job_name: time.time() for job_name in self.job_names}

        for job_name in self.job_names:
            frame = ttk.Frame(self.root)
            frame.pack()

            # Keep track of all job-related frames for updating purposes
            self.job_frames.append(frame)

            job_name_label = ttk.Label(frame, text=f"Job name: {job_name}", font=("gothic", 16, "bold"))
            job_name_label.pack()

            speed_mean_label = ttk.Label(frame, text="Speed mean: ", font=("gothic", 15, "normal"))
            speed_mean_label.pack()

            speed_latest_label = ttk.Label(frame, text="Speed latest: ", font=("gothic", 15, "normal"))
            speed_latest_label.pack()

            status_label = ttk.Label(frame, text="Status: ")
            status_label.pack()

        self.root.after(0, self.update_all)

        self.root.mainloop()

    def fetch_job_names(self, wildcard=False):
        if wildcard:
            first_job_line = 0
            # Double grep if there is an asterisk in job_names (i.e., wildcard)
            runai_command = f"runai list | grep Running | grep {''.join(self.job_names[0].split('*'))}"
        else:
            first_job_line = 1
            runai_command = f"runai list | grep Running"
        # Get job list
        job_list = subprocess.Popen(
            ["ssh", f"{self.username}@{self.server_address}", runai_command],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        # Get logs as string
        job_list = job_list.stdout.read().decode("latin-1")

        # Split according to each job
        job_list = job_list.split("\n")
        self.job_names = [x.split()[0] for x in job_list[first_job_line:-1]]

    def get_job_details(self, job_name):
        # Get job description
        job_description = subprocess.Popen(
            ["ssh", f"{self.username}@{self.server_address}", "runai", "describe", "job", job_name], stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

        job_description = job_description.stdout.read().decode("latin-1")

        if "could not find any job" in job_description:
            return -1, -1, "Job not found"
        # Determine if pending or failed
        elif "FAILED" in job_description:
            return -1, -1, "Job failed"
        elif "PENDING" in job_description:
            return -1, -1, "Job pending"

        # Get logs
        job_logs = subprocess.Popen(
            ["ssh", f"{self.username}@{self.server_address}", "runai", "logs", job_name], stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

        # Get logs as string
        job_logs = job_logs.stdout.read().decode("latin-1")

        # Get latest iteration speeds
        regex = re.compile("([0-9]*[.][0-9]*s/it|[0-9]*[.][0-9]*it/s)")
        speed_matches = regex.findall(job_logs)

        # Account for the fact that the job might have just started and not have any speed matches yet
        if len(speed_matches) == 0:
            return -1, -1, "Job just started: No speed matches yet"

        # Isolate floats
        if self.logging_mode == "s/it":
            speed_matches = [float(x.split("s/it")[0]) if "s/it" in x else 1/float(x.split("it/s")[0])
                             for x in speed_matches]
        else:
            speed_matches = [1/float(x.split("s/it")[0]) if "s/it" in x else float(x.split("it/s")[0])
                             for x in speed_matches]
        try:
            speed_mean = np.mean(speed_matches[-self.speed_history:])
            speed_latest = speed_matches[-1]
        except IndexError:
            # Job probably just resumed/ was submitted
            speed_latest = -1
            speed_mean = -1

        # Isolate job node
        regex = re.compile(r'dgx[\w-]+(?=/)')
        job_node = regex.findall(job_description)[0].split("/")[0]

        return speed_mean, speed_latest, job_node

    def update_speed(self, frame, job_name):
        speed_mean, speed_latest, node = self.get_job_details(job_name)

        if speed_latest == -1 and speed_mean == -1:
            for line_index in range(1, len(frame.winfo_children()) - 1):
                # While frame has more than 2 children (i.e., more than just the job name and job status labels)
                # Delete the second label (i.e., the speed-related label)
                while len(frame.winfo_children()) > 2:
                    existing_widget = frame.winfo_children()[1]
                    existing_widget.destroy()
            # Update job with specific error returned by investigating the job description
            frame.winfo_children()[-1].config(
                text=f"{node}\n\n", style="FP.TLabel", font=("gothic", 16, "bold")
            )

        else:
            # If length of frame is 2, job was in a pending/ failed/ non-existent state before, add speed-related labels
            if len(frame.winfo_children()) == 2:
                speed_mean_label = ttk.Label(frame, text="Speed mean: ", font=("gothic", 15, "normal"))
                speed_mean_label.pack()

                speed_latest_label = ttk.Label(frame, text="Speed latest: ", font=("gothic", 15, "normal"))
                speed_latest_label.pack()
            # Access labels within the frame
            frame.winfo_children()[-3].config(text=f"Speed mean: {speed_mean:.2f}{self.logging_mode}")
            frame.winfo_children()[-2].config(text=f"Speed latest: {speed_latest:.2f}{self.logging_mode}")
            # Update node dictionary or add node key if not present
            # https://stackoverflow.com/questions/12905999/how-to-create-key-or-append-an-element-to-key
            self.node_dict.setdefault(node, []).append(speed_latest)

            # Update status box
            if self.logging_mode == "s/it":
                if speed_latest > 50:
                    # Just update status box
                    frame.winfo_children()[-1].config(
                        text=f"{node} Status: Extreme slowdown!\n\n",
                        style="FR.TLabel",
                        font=("gothic", 18, "bold"),
                    )
                elif speed_latest > 10:
                    # Just update status box
                    frame.winfo_children()[-1].config(
                        text=f"{node} Status: Worrying\n\n",
                        style="FO.TLabel",
                        font=("gothic", 16, "bold"),
                    )
                elif 5 < speed_latest < 10:
                    # Just update status box
                    frame.winfo_children()[-1].config(
                        text=f"{node} Status: Normal\n\n",
                        style="FG.TLabel",
                        font=("gothic", 15, "bold"),
                    )
                elif speed_latest > 0:
                    frame.winfo_children()[-1].config(
                        text=f"{node} Status: Excellent (for now)\n\n",
                        style="FB.TLabel",
                        font=("gothic", 15, "bold"),
                    )
            else:
                if speed_latest > 1/5:
                    # Just update status box
                    frame.winfo_children()[-1].config(
                        text=f"{node} Status: Excellent (for now)\n\n",
                        style="FB.TLabel",
                        font=("gothic", 15, "bold"),
                    )
                elif 1/5 < speed_latest < 1/10:
                    # Just update status box
                    frame.winfo_children()[-1].config(
                        text=f"{node} Status: Normal\n\n",
                        style="FG.TLabel",
                        font=("gothic", 15, "bold"),
                    )
                elif 1/10 > speed_latest > 1/50:
                    # Just update status box
                    frame.winfo_children()[-1].config(
                        text=f"{node} Status: Worrying\n\n",
                        style="FO.TLabel",
                        font=("gothic", 16, "bold"),
                    )
                else:
                    frame.winfo_children()[-1].config(
                        text=f"{node} Status: Extreme slowdown!\n\n",
                        style="FR.TLabel",
                        font=("gothic", 18, "bold"),
                    )

        self.current_times[job_name] = time.time()

    def update_all(self):
        # Get time
        # self.current_time = time.time()
        # Update job-related frames
        for frame, job_name in zip(self.job_frames, self.job_names):
            self.update_speed(frame, job_name)

        # Clear previous labels
        for widget in self.node_frame.winfo_children():
            widget.destroy()

        # Update node label
        last_update_text = f"Last update: {time.time() - self.current_time:.1f}s\n"
        ttk.Label(self.node_frame, text=last_update_text, font=("gothic", 16, "bold")).pack()
        node_text = "Node info"
        ttk.Label(self.node_frame, text=node_text, font=("gothic", 20, "bold")).pack()
        for node, node_speed in self.node_dict.items():
            if node == "Job not found":
                pass
            else:
                mean_node_speed = np.mean(node_speed)
                if self.logging_mode == "s/it":
                    if mean_node_speed > 50:
                        node_message = "Extreme slowdown!"
                        node_style = "FR.TLabel"
                        node_font = ("gothic", 18, "bold")
                    elif mean_node_speed > 10:
                        node_message = "Worrying"
                        node_style = "FO.TLabel"
                        node_font = ("gothic", 16, "bold")
                    elif 5 < mean_node_speed < 10:
                        node_message = "Normal"
                        node_style = "FG.TLabel"
                        node_font = ("gothic", 15, "bold")
                    else:
                        node_message = "Excellent (for now)"
                        node_style = "FB.TLabel"
                        node_font = ("gothic", 15, "bold")
                else:
                    if mean_node_speed > 1/5:
                        node_message = "Excellent (for now)"
                        node_style = "FB.TLabel"
                        node_font = ("gothic", 15, "bold")
                    elif 1/5 > mean_node_speed > 1/10:
                        node_message = "Normal"
                        node_style = "FG.TLabel"
                        node_font = ("gothic", 15, "bold")
                    elif 1/10 > mean_node_speed > 1/50:
                        node_message = "Worrying"
                        node_style = "FO.TLabel"
                        node_font = ("gothic", 16, "bold")
                    else:
                        node_message = "Extreme slowdown!"
                        node_style = "FR.TLabel"
                        node_font = ("gothic", 18, "bold")

                # node_text += f"{node}: {mean_node_speed:.2f}\n"
                ttk.Label(self.node_frame, text=f"{node}: {node_message}", font=node_font, style=node_style).pack()

        # Add a space
        ttk.Label(self.node_frame, text="\n\n").pack()

        # Reset node dictionary
        self.node_dict = {}

        # Update time
        self.current_time = time.time()

        # Schedule the next update
        self.root.after(self.loop_timing, self.update_all)


if __name__ == "__main__":
    # Parse arguments using argparse not importing from utils
    import argparse

    parser = argparse.ArgumentParser(description="Job speed monitor")
    parser.add_argument("--username", type=str, help="RunAI username")
    parser.add_argument("--server_address", type=str, default="dgx1a", help="Server address or alias")
    parser.add_argument("--job_names", type=str, nargs="+", help="Job name")
    parser.add_argument("--speed_history", type=int, help="How many iterations to average speed over", default=100)
    parser.add_argument("--loop_timing", type=int, help="How often to update GUI in s", default=100)
    parser.add_argument("--logging_mode", type=str, help="Logging preference: s/it or it/s",
                        default="s/it")
    args = parser.parse_args()

    job = SpeedGUI(username=args.username,
                   server_address=args.server_address,
                   job_names=args.job_names,
                   speed_history=args.speed_history,
                   loop_timing=args.loop_timing * 1000,
                   logging_mode=args.logging_mode)
