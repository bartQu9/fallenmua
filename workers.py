from multiprocessing import Process
import logging


class MsgWorker(Process):
    def __init__(self, task_queue, result_queue):
        super().__init__()
        logging.debug("Initializing {0}".format(self.name))
        self.task_queue = task_queue
        self.result_queue = result_queue

    def run(self):
        proc_name = self.name
        logging.debug("Running {0}".format(proc_name))
        while True:
            next_package = self.task_queue.get()

            if next_package is None:  # Poison pill means shutdown
                logging.debug("Exiting {0}".format(proc_name))
                self.task_queue.task_done()
                break

            env_from = next_package[0]
            env_to = next_package[1]
            next_task = next_package[2]

            logging.debug("{0}: Getting task {1}".format(proc_name, next_task))
            message = next_task()
            self.task_queue.task_done()
            self.result_queue.put([env_from, env_to, message])
        return
