from flask import (
    Flask,
    jsonify,
    request,
    render_template,
    redirect,
    make_response,
    send_file,
)

from hardware import Hardware

app = Flask(__name__)
from enum import Enum
import uuid
import random

rd = random.Random()
rd.seed(0)
import sys
import queue
import json
from json import JSONEncoder
import datetime
import time
from flask_recaptcha import ReCaptcha


app = Flask(__name__)
app.config.from_pyfile("../../settings.cfg")
recaptcha = ReCaptcha(app=app)

# a status enum
class Status:
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"


# a class for queued, running, or completed jobs
class Job:
    def __init__(self, user, name, git_url):
        self.id = str(uuid.UUID(int=rd.getrandbits(128)))  # a random id
        self.name = name  # github project name
        self.user = user  # github user id
        self.git_url = git_url  # github hrl
        self.status = Status.QUEUED  # job status
        self.hardware = None  # the hardware the job is/was run on, none if queued
        self.results = "Results pending."  # job results
        self.data = (
            None
        )  # observations, actions, reqards, and times for the job data points
        self.queued_time = time.time()
        self.running_time = None
        self.completed_time = None

    def __hash__(
        self
    ):  # define the hash function so that Job objects can be used in a set
        return hash(self.id)

    def __eq__(self, other):  # also so Job objects can be used in sets
        if isinstance(other, Job):
            return self.id == other.id
        else:
            return False

    def __dict__(self):  # a function for making the job serializable
        return {
            "id": self.id,
            "name": self.name,
            "user": self.user,
            "git_url": self.git_url,
            "results": self.results,
            "data": self.data,
            "status": self.status,
            "hardware": self.hardware,
            "queued_time": self.queued_time,
            "running_time": self.running_time,
            "completed_time": self.completed_time,
        }


# a custom json encoder which replaces the default and allows Job objects to be jsonified
class JSONEncoderJob(JSONEncoder):
    def default(self, job):
        try:
            if isinstance(
                job, Job
            ):  # if the object to be encoded is a job, use the dict() function
                return job.__dict__()
        except TypeError:
            pass
        return JSONEncoder.default(self, job)


# replace the default encoder
app.json_encoder = JSONEncoderJob


def format_datetime(value):
    return datetime.datetime.fromtimestamp(value).strftime("%m/%d/%y %H:%M:%S")


app.jinja_env.filters["datetime"] = format_datetime

# a dictionary of all jobs
# TODO: replace with a database


jobs = {}
queued = queue.Queue()  # a queue for the queued jobs
running = {}  # a set of running jobs
completed = queue.Queue(maxsize=20)  # a queue of recently completed jobs

hardware_dict = {
    'Nmar': Hardware('Omar'),
    'Goose': Hardware('Goose'),
    'Nicki': Hardware('Nicki'),
    'Beth': Hardware('Beth')
}


def reset_jobs():
    global jobs, queued, running, completed
    jobs = {}

    queued = queue.Queue()  # a queue for the queued jobs
    running = {}  # a set of running jobs
    completed = queue.Queue(maxsize=20)  # a queue of recently completed jobs

def check_ip(ip):
    return (ip in app.config["PI_IP"])


@app.route("/reset")
def reset_route():
    if not check_ip(request.remote_addr):
        print("reset request from non-pi ip")
        return make_response("", 403)
    reset_jobs()
    return redirect("/")


@app.route("/")
def base_route():
    # return send_file("static/index.html")
    return render_template("index.html")

@app.route("/status")
def status_route():
    return render_template("hardware.html")

@app.route("/hardware")
def hardware_route():
    return jsonify(
        sorted(
            [{'name':hardware.name, 'status':"ONLINE" if hardware.is_alive() else "OFFLINE"} for hardware in hardware_dict.values()],
            key=lambda hw: hw['name']
        )
    )


@app.route("/job/<string:id>", methods=["GET"])
def job_page_route(id):
    if id in jobs:
        return render_template("job.html", job=jobs[id])
    else:
        return redirect("/")


@app.route("/submit", methods=["GET"])
def submit_page_route():
    return render_template("submit.html")


@app.route("/job", methods=["POST", "GET"])
def job_route():
    if request.method == "POST":
        new_job = Job(request.form["user"], request.form["name"], request.form["git"])
        jobs[new_job.id] = new_job  # add to database
        queued.put(new_job)  # add to queue
        return redirect("/")
    if request.method == "GET":
        return jsonify(
            {
                "queued": sorted(list(queued.queue), key=lambda job: -job.queued_time),
                "running": sorted(
                    list(running.values()), key=lambda job: -job.running_time
                ),
                "completed": sorted(
                    list(completed.queue), key=lambda job: -job.completed_time
                ),
            }
        )


@app.route("/job/pop", methods=["GET"])
def job_pop_route():
    if request.method == "GET":
        if not check_ip(request.remote_addr):
            print("pop request from non-pi ip")
            return make_response("", 403)

        req_hardware = request.args.get('hardware')
        print(req_hardware)
        if req_hardware in hardware_dict:
            hardware_dict[req_hardware].heartbeat()

        if not queued.empty():

            pop_job = queued.get()  # get job from queue
            #pop_job.hardware = (
            #    "Pendulum-1"
            #)  # set hardware of job TODO: actually set this to a meaningful value
            pop_job.hardware = req_hardware

            running[pop_job.id] = pop_job  # add to running dict
            pop_job.status = Status.RUNNING
            pop_job.running_time = time.time()
            # return jsonify({"git_url": pop_job.git_url, "id": pop_job.id})
            return jsonify(pop_job)
        else:
            return make_response("", 204)


@app.route("/job/<string:id>/results", methods=["PUT"])
def job_results_route(id):
    if request.method == "PUT":
        if not check_ip(request.remote_addr):
            print("results request from non-pi ip")
            return make_response("", 403)
        if id in jobs:
            job = jobs[id]  # look up job
            del running[id]  # remove from running dict

            completed.put(job)  # add to completed buffer

            req_data = request.get_json()

            job.status = Status.COMPLETE
            job.results = req_data["results"][2:-1]
            job.data = req_data["data"]
            print(job.data)
            job.completed_time = time.time()
            return make_response("", 200)
        else:
            return make_response("", 404)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "prod":
        app.run(port=80, host="0.0.0.0")
    else:
        app.run(debug=True)
