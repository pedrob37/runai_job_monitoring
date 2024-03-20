import copy
import re
import subprocess
import time
import tkinter as tk
from tkinter import ttk, PhotoImage
from PIL import ImageTk as itk
import numpy as np
import json


class SpeedGUI(object):
    def __init__(self, username, server_address, job_names,
                 speed_history=100, loop_timing=10000, logging_mode="s/it", optimal_upper_limit=5,
                 dynamic_job_list=True,
                 remote_aggregation=False,
                 festive=False):

        # Assigning variables
        self.username = username
        self.server_address = server_address
        self.job_names = job_names
        self.speed_history = speed_history
        self.loop_timing = loop_timing
        self.logging_mode = logging_mode
        self.optimal_upper_limit = optimal_upper_limit
        self.current_time = time.time()
        self.remote_aggregation = remote_aggregation
        self.dynamic_job_list = dynamic_job_list
        self.festive = festive

        self.node_dict = {}

        self.root = tk.Tk()
        self.root.title("Marshall Monitor" if username == "pedro" else "DGX Monitor")
        self.root.attributes("-topmost", True)

        # Initialising empty variables to be assigned later by the get_job_list method
        self.gif_label = None
        self.frames = None
        self.ind = None
        self.image = None
        self.current_times = None
        self.node_frame = None
        self.job_frames = None

        # Set up styles
        self.style = ttk.Style()
        self.style.configure("BW.TLabel", background="white")
        self.style.configure("FB.TLabel", foreground="black")
        self.style.configure("FR.TLabel", foreground="red")
        self.style.configure("FO.TLabel", foreground="dark orange")
        self.style.configure("FG.TLabel", foreground="green")
        self.style.configure("FB.TLabel", foreground="blue")
        self.style.configure("FP.TLabel", foreground="purple")

        self.root.after(0, self.update_all)

        if self.dynamic_job_list:
            self.old_job_names = None
            self.wildcard_presence = False if not self.job_names else (True if "*" in self.job_names[0] else False)
            self.first_pass = True

        self.root.mainloop()
        
    def get_job_list(self):
        if self.dynamic_job_list:
            if not self.first_pass:
                # Check if current job list is different from previous one
                self.old_job_names = copy.deepcopy(self.job_names)

                if self.wildcard_presence:
                    self.fetch_job_names(wildcard=True)
                else:
                    self.fetch_job_names(wildcard=False)

                # If job list is the same as before, no need for a full update
                if self.old_job_names == self.job_names:
                    return

        # Account for wildcards and missing job names
        if not self.job_names:
            self.fetch_job_names(wildcard=False)
        elif "*" in self.job_names[0]:
            assert len(self.job_names) == 1, "Only one wildcard supported!"
            self.fetch_job_names(wildcard=True)

        # Starting times
        self.current_times = {job_name: time.time() for job_name in self.job_names}

        # If not first pass, destroy previous frames to fully update job list in case of changes
        if self.dynamic_job_list:
            if not self.first_pass:
                self.node_frame.destroy()
                for frame in self.job_frames:
                    frame.destroy()

        # Separate frame for nodes
        self.job_frames = []
        self.node_frame = ttk.Frame(self.root)
        self.node_frame.pack()

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

        self.ind = 0

        # Festive
        if self.festive:
            from urllib.request import urlopen
            from PIL import Image
            from io import BytesIO
            URL = "https://i.gifer.com/origin/35/353fb026a4147fc679d3292fdd59663f_w200.gif"

            gif_data = urlopen(URL).read()
            self.image = Image.open(BytesIO(gif_data))
            self.ind = 0
            self.frames = [itk.PhotoImage(self.image.copy()) for _ in range(self.image.n_frames)]

            self.gif_label = ttk.Label(image=self.frames[self.ind])
            self.gif_label.pack()
            self.root.after(0, self.update_gifs)

    def update_gifs(self):
        from PIL import Image
        # https://stackoverflow.com/questions/28518072/play-animations-in-gif-with-tkinter
        self.ind += 1
        if self.ind == len(self.frames):
            self.ind = 0

        # Reload the image for each frame
        self.image.seek(self.ind)
        self.frames[self.ind] = itk.PhotoImage(self.image.resize((200, 200), Image.LANCZOS).copy())

        self.gif_label.configure(image=self.frames[self.ind])
        self.root.after(120, self.update_gifs)

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

        # Exclude inference jobs
        self.job_names = [job_name for job_name in self.job_names if "inf-" not in job_name]

    def get_job_details(self, job_name):
        # Get job description
        job_description = subprocess.Popen(
            ["ssh", f"{self.username}@{self.server_address}", "runai", "describe", "job", job_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

        job_description = job_description.stdout.read().decode("latin-1")

        if "could not find any job" in job_description:
            return -1, -1, "Job not found", "N/A"
        # Determine if pending or failed
        elif "ERROR" in job_description:
            return -1, -1, "Job failed", "N/A"
        elif "PENDING" in job_description:
            return -1, -1, "Job pending", "N/A"

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
            return -1, -1, "Job just started: No speed matches yet", "N/A"

        # Isolate floats
        if self.logging_mode == "s/it":
            speed_matches = [float(x.split("s/it")[0]) if "s/it" in x else 1 / float(x.split("it/s")[0])
                             for x in speed_matches]
        else:
            speed_matches = [1 / float(x.split("s/it")[0]) if "s/it" in x else float(x.split("it/s")[0])
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

        # Get job age
        job_description_lines = job_description.split("\n")

        # Find line that contains job age
        relevant_line = job_description_lines.index([x for x in job_description_lines if x.startswith("POD")][0]) + 1
        job_age = job_description_lines[relevant_line].split()[-2]
        return speed_mean, speed_latest, job_node, job_age

    def update_speed(self, frame, job_name):
        speed_mean, speed_latest, node, age = self.get_job_details(job_name)

        if speed_latest == -1 and speed_mean == -1:
            for line_index in range(1, len(frame.winfo_children()) - 1):
                # While frame has more than 2 children (i.e., more than just the job name and job status labels)
                # Delete the second label (i.e., the speed-related label)
                while len(frame.winfo_children()) > 2:
                    existing_widget = frame.winfo_children()[1]
                    existing_widget.destroy()
            # Update job with specific error returned by investigating the job description
            frame.winfo_children()[-1].config(
                text=f"{node}\n\n", style="FP.TLabel", font=("gothic", 16, "bold"))
        else:
            # If length of frame is 2, job was in a pending/ failed/ non-existent state before, add speed-related labels
            if len(frame.winfo_children()) == 2:
                speed_mean_label = ttk.Label(frame, text="Speed mean: ", font=("gothic", 15, "normal"))
                speed_mean_label.pack()

                speed_latest_label = ttk.Label(frame, text="Speed latest: ", font=("gothic", 15, "normal"))
                speed_latest_label.pack()
            # Access labels within the frame
            frame.winfo_children()[-4].config(text=f"{job_name} ({age})")
            frame.winfo_children()[-3].config(text=f"Speed mean: {speed_mean:.2f}{self.logging_mode}",
                                              style="BB.TLabel")
            frame.winfo_children()[-3].config(text=f"Speed mean: {speed_mean:.2f}{self.logging_mode}",
                                              style="BB.TLabel")
            frame.winfo_children()[-2].config(text=f"Speed latest: {speed_latest:.2f}{self.logging_mode}")
            # Update node dictionary or add node key if not present
            # https://stackoverflow.com/questions/12905999/how-to-create-key-or-append-an-element-to-key
            self.node_dict.setdefault(node, []).append(speed_latest)

            # Update status box
            if self.logging_mode == "s/it":
                if speed_latest > 10 * self.optimal_upper_limit:
                    # Just update status box
                    frame.winfo_children()[-1].config(
                        text=f"{node} Status: Extreme slowdown!\n\n",
                        style="FR.TLabel",
                        font=("gothic", 18, "bold"),
                    )
                elif speed_latest > 2 * self.optimal_upper_limit:
                    # Just update status box
                    frame.winfo_children()[-1].config(
                        text=f"{node} Status: Worrying\n\n",
                        style="FO.TLabel",
                        font=("gothic", 16, "bold"),
                    )
                elif self.optimal_upper_limit < speed_latest < 2 * self.optimal_upper_limit:
                    # Just update status box
                    frame.winfo_children()[-1].config(
                        text=f"{node} Status: Normal\n\n",
                        style="FG.TLabel",
                        font=("gothic", 15, "bold"),
                    )

                else:
                    frame.winfo_children()[-1].config(
                        text=f"{node} Status: Excellent (for now)\n\n",
                        style="FB.TLabel",
                        font=("gothic", 15, "bold"),
                    )
            else:
                if speed_latest > 1 / self.optimal_upper_limit:
                    # Just update status box
                    frame.winfo_children()[-1].config(
                        text=f"{node} Status: Excellent (for now)\n\n",
                        style="FB.TLabel",
                        font=("gothic", 15, "bold"),
                    )
                elif 1 / self.optimal_upper_limit < speed_latest < 1 / (2 * self.optimal_upper_limit):
                    # Just update status box
                    frame.winfo_children()[-1].config(
                        text=f"{node} Status: Normal\n\n",
                        style="FG.TLabel",
                        font=("gothic", 15, "bold"),
                    )
                elif 1 / (2 * self.optimal_upper_limit) > speed_latest > 1 / (10 * self.optimal_upper_limit):
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
        # Update job list
        self.get_job_list()

        # After first pass, will need to destroy previous frames to fully update job list in case of changes
        if self.dynamic_job_list:
            if self.first_pass:
                self.first_pass = False

        # Update job-related frames
        for frame, job_name in zip(self.job_frames, self.job_names):
            self.update_speed(frame, job_name)

        # Clear previous labels
        for widget in self.node_frame.winfo_children():
            widget.destroy()

        # Update node label
        last_update_text = f"Last update: {time.time() - self.current_time:.1f}s\n"
        ttk.Label(self.node_frame, text=last_update_text, font=("gothic", 16, "bold")).pack()
        node_text = f"Node info{' (Remote aggregation)' if self.remote_aggregation else ''}"
        ttk.Label(self.node_frame, text=node_text, font=("gothic", 20, "bold")).pack()

        if self.remote_aggregation:
            # Loop through user remote logs
            remote_path = f"/nfs/project/AMIGO/Monitor_Aggregation"
            json_files = subprocess.Popen(
                ["ssh", f"{self.username}@{self.server_address}",
                 f"ls -t {remote_path}/*_node_info.json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL)

            json_files = json_files.stdout.read().decode("latin-1").split("\n")[:-1]

            # Aggregate node dictionary for all users
            aggregate_node_dict = {}
            for json_file in json_files:
                ssh_command = f'ssh {self.username}@{self.server_address} "cat {json_file}"'
                loaded_node_dict = subprocess.check_output(ssh_command,
                                                           shell=True, stderr=subprocess.DEVNULL).decode('utf-8')
                result_dict = json.loads(loaded_node_dict)
                # Convert to standard set in current execution: s/it or it/s
                if self.logging_mode == "s/it" and result_dict["logging_mode"] == "it/s":
                    result_dict.pop("logging_mode")
                    result_dict = {key: [1 / value for value in values] for key, values in result_dict.items()}
                elif self.logging_mode == "it/s" and result_dict["logging_mode"] == "s/it":
                    result_dict.pop("logging_mode")
                    result_dict = {key: [1 / value for value in values] for key, values in result_dict.items()}
                else:
                    result_dict.pop("logging_mode")
                for agg_key, agg_value in result_dict.items():
                    aggregate_node_dict.setdefault(agg_key, []).extend(agg_value)

            # Log node usage by saving to cluster using ssh
            if self.remote_aggregation:
                # Convert the dictionary to a remote json for user-aggregate metrics
                self.node_dict["logging_mode"] = self.logging_mode
                json_data = json.dumps(self.node_dict)

                # Save JSON data to a file on the remote server using Python
                json_save_path = f"{remote_path}/{self.username}_node_info.json"
                ssh_command = f'ssh {self.username}@{self.server_address} "cat > {json_save_path}"'
                subprocess.run(ssh_command, shell=True, input=json_data.encode(), stderr=subprocess.DEVNULL)

        # Loop through either node dictionary or aggregate node dictionary
        for node, node_speed in (self.node_dict.items() if not self.remote_aggregation else aggregate_node_dict.items()):
            if node == "Job not found":
                pass
            else:
                mean_node_speed = np.mean(node_speed)
                if self.logging_mode == "s/it":
                    if mean_node_speed > 10 * self.optimal_upper_limit:
                        node_message = "Extreme slowdown!"
                        node_style = "FR.TLabel"
                        node_font = ("gothic", 18, "bold")
                    elif mean_node_speed > 2 * self.optimal_upper_limit:
                        node_message = "Worrying"
                        node_style = "FO.TLabel"
                        node_font = ("gothic", 16, "bold")
                    elif self.optimal_upper_limit < mean_node_speed < 2 * self.optimal_upper_limit:
                        node_message = "Normal"
                        node_style = "FG.TLabel"
                        node_font = ("gothic", 15, "bold")
                    else:
                        node_message = "Excellent (for now)"
                        node_style = "FB.TLabel"
                        node_font = ("gothic", 15, "bold")
                else:
                    if mean_node_speed > 1 / self.optimal_upper_limit:
                        node_message = "Excellent (for now)"
                        node_style = "FB.TLabel"
                        node_font = ("gothic", 15, "bold")
                    elif 1 / self.optimal_upper_limit > mean_node_speed > 1 / (2 * self.optimal_upper_limit):
                        node_message = "Normal"
                        node_style = "FG.TLabel"
                        node_font = ("gothic", 15, "bold")
                    elif 1 / (2 * self.optimal_upper_limit) > mean_node_speed > 1 / (10 * self.optimal_upper_limit):
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
    parser.add_argument("--server_address", type=str, help="Server address or alias",
                        default="dgx1a")
    parser.add_argument("--job_names", type=str, nargs="+", help="Job name")
    parser.add_argument("--speed_history", type=int, help="How many iterations to average speed over",
                        default=100)
    parser.add_argument("--loop_timing", type=int, help="How often to update GUI in s",
                        default=100)
    parser.add_argument("--optimal_upper_limit", type=float, help="Optimal upper limit for speed in s/it",
                        default=5)
    parser.add_argument("--logging_mode", type=str, help="Logging preference: s/it or it/s",
                        default="s/it")
    parser.add_argument('--dynamic_job_list', action='store_true', help="Automatically update job list")
    parser.add_argument('--festive', action='store_true')
    parser.add_argument('--remote_aggregation', action='store_true')
    args = parser.parse_args()

    job = SpeedGUI(username=args.username,
                   server_address=args.server_address,
                   job_names=args.job_names,
                   speed_history=args.speed_history,
                   loop_timing=args.loop_timing * 1000,
                   optimal_upper_limit=args.optimal_upper_limit,
                   dynamic_job_list=args.dynamic_job_list,
                   logging_mode=args.logging_mode,
                   remote_aggregation=args.remote_aggregation,
                   festive=args.festive)
