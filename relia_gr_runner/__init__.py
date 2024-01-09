import os
import time
import click
from flask import Flask

from config import configurations

from gnuradio import fft
from gnuradio.fft import window

def create_app(config_name: str = 'default'):
    # Based on Flasky https://github.com/miguelgrinberg/flasky

    app = Flask(__name__)
    app.config.from_object(configurations[config_name])

    from .processor import Processor
    from .grc_manager import GrcManager
    from .scheduler import TaskAssignment

    @app.cli.command('process-tasks')
    def process_tasks():
        """
        Process tasks
        """
        print(f"[{time.asctime()}] Creating cache for fft.fft_vcc with 1024...")
        fft.fft_vcc(1024, True, window.blackmanharris(1024), True, 1)
        print(f"[{time.asctime()}] Cache created")
        processor = Processor(running_single_task=False)
        processor.run_forever()

    @app.cli.command('create-gnuradio-fft-caches')
    @click.option("--start", type=int, default=1)
    @click.option("--end", type=int, default=2**14 + 1)
    @click.option("--step", type=int, default=1)
    def create_caches(start, end, step):
        """
        These files take a long time to be created, but then they are cached.
        """
        for num in range(start, end + 1, step):
            print(f"[{time.asctime()}] Creating cache for fft.fft_vcc with {num}...", flush=True)
            t0 = time.time()
            fft.fft_vcc(num, True, window.blackmanharris(num), True, 1)
            tf = time.time()
            elapsed = tf - t0
            print(f"[{time.asctime()}] Cache created", flush=True)

            if elapsed > 5:
                # If the CPU has been running for a while, give it a break to avoid increasing temperature
                time.sleep(1)

            if num % 256 == 0:
                print(f"[{time.asctime()}] Creating backup...", flush=True)
                backup_content = open(os.path.expanduser("~/.gr_fftw_wisdom"), 'r').read()
                new_filename = os.path.expanduser(f"~/.backup-{num}-gr_fftw_wisdom")
                open(new_filename, 'w').write(backup_content)
                print(f"[{time.asctime()}] Backup created and stored at: {new_filename}", flush=True)

    @app.cli.command("process-single-task")
    @click.option("--grc-filename", type=click.Path(exists=True))
    @click.option("--directory", type=click.Path(exists=True))
    @click.option("--timeout", type=int, default=30)
    def process_task(grc_filename: str, directory: str, timeout: int):
        """
        Compile and run a GRC file, without interacting servers.
        """
        processor = Processor(running_single_task=True)

        grc_original_content = open(grc_filename).read()
        grc_manager = GrcManager(grc_original_content)
        grc_manager.process()

        app.config['MAX_GR_PYTHON_EXECUTION_TIME'] = timeout
        
        directory = os.path.abspath(directory)

        fake_session_id = "non.existing.session"
        device_data = TaskAssignment(sessionIdentifier=fake_session_id, taskIdentifier="invalid.task.id", maxTime=3600, grcFile="foo.grc", grcFileContent=grc_original_content)
        processor.run_task_in_directory(directory,  grc_manager, fake_session_id, device_data, init_time=time.perf_counter(), target_filename='target_file')

    @app.cli.command("compile-grc")
    @click.option("--grc-filename", type=click.Path(exists=True))
    @click.option("--directory", type=click.Path(exists=True))
    def compile_grc(grc_filename: str, directory: str):
        """
        Compile, without running, a grc file on a folder.
        """
        processor = Processor(running_single_task=True)

        grc_original_content = open(grc_filename).read()
        grc_manager = GrcManager(grc_original_content)
        grc_manager.process()

        directory = os.path.abspath(directory)

        fake_session_id = "non.existing.session"
        device_data = TaskAssignment(sessionIdentifier=fake_session_id, taskIdentifier="invalid.task.id", maxTime=3600, grcFile="foo.grc", grcFileContent=grc_original_content)
        processor.compile_grc_filename_into_python(directory,  grc_manager, fake_session_id, device_data, init_time=time.perf_counter())
        
    return app

