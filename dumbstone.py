"""
Wrapper to dumb down leela zero dynamically.
"""
import os
import re
import sys
import time

from configparser import ConfigParser
from queue import Queue, Empty
from subprocess import PIPE, Popen
from threading import Thread


def stream_reader(stream, queue):
    """
    Read lines from stream and put them into queue.
    :param stream: where to read lines from
    :param queue: where to put the lines into
    """
    for line in stream:
        if isinstance(line, str):
            queue.put(line)
        else:
            queue.put(line.decode())
    stream.close()


def start_reader(stream):
    """
    Start reading lines from the given stream, putting them in a freshly
    created queue and return the queue.

    :param stream: stream to read from
    :returns: create queue
    """
    queue = Queue()
    reader = Thread(target=stream_reader, args=(stream, queue))
    reader.daemon = True
    reader.start()
    return queue


def dump_to_stream(queue, stream):
    """Dump queue content to stream, non-blocking.
    :param queue: where to get content from
    :param stream: where to dump content to
    """
    res = False
    while True:
        try:
            line = queue.get_nowait()
        except Empty:
            return res
        res = True
        stream.write(line)
        stream.flush()


class LzWrapper:
    """
    Wrapper for Leela Zero process.
    """
    _VARIATION = re.compile(r" *([^ ]*) -> .*\(V: ([^%]*)%\).*$")

    def __init__(self, lz_binary, weights, visits, log_f):
        """
        Start Leela Zero wrapper.

        :param lz_binary: path to Leela Zero binary
        :param weights: path to weights file
        :param visits: number of visits to use
        :param log_f: function to log messages
        """
        self._log = log_f
        cmd_line = [lz_binary]
        cmd_line += ['-w', weights]
        cmd_line += ['-v', visits]
        cmd_line += ['-g']
        self._log("Starting LZ")
        self._lz = Popen(cmd_line,
                         stdin=PIPE, stdout=PIPE, stderr=PIPE,
                         bufsize=1)

        self._lz_out = start_reader(self._lz.stdout)
        self._lz_err = start_reader(self._lz.stderr)
        self._log("LZ started")

    def dump_stderr(self):
        """
        Write to sys.stderr everything LZ has to say on stderr, return True if
        something was outputted, False otherwise.
        """
        return dump_to_stream(self._lz_err, sys.stderr)

    def dump_stdout(self):
        """
        Write to sys.stdout everything LZ has to say on stdout, return True if
        something was outputted, False otherwise.
        """
        return dump_to_stream(self._lz_out, sys.stdout)

    def _consume_stdout_until_ready(self):
        while True:
            out = self._lz_out.get()  # blocking!
            self._log("Consumed: {}".format(out.strip()))
            if out[0:1] == '=':
                return

    def dump_stdout_until_ready(self):
        """
        Dump LZ's stdout to sys.stdout until GTP normal reply (starting with
        '=' or '?'); inclusive.
        """
        while True:
            out = self._lz_out.get()  # blocking!
            sys.stdout.write(out)
            sys.stdout.flush()
            if out[0:1] in ['=', '?']:
                return

    def pass_to_lz(self, command):
        """
        Pass the command to LZ without any modifications.

        :param command: ASCII string, the command to pass to LZ. Expected to
        end with \r\n
        :param dump_stdout: if True, dumps LZ's stdout to sys.stdout until '=
        ...' GTP line (inclusive)
        """
        command_bytes = bytes(command, encoding='ascii')
        self._lz.stdin.write(command_bytes)
        self._lz.stdin.flush()

    def _wait_for_move(self):
        while True:
            out = self._lz_out.get()  # blocking!
            if out[0:1] == '=':
                return out[2:].strip()
            else:
                sys.stdout.write(out)
                sys.stdout.flush()

    def genmove(self, color, probability=50.0):
        """
        Generate move.

        Will output things to stderr and stdout.

        :param color: player to generate move for ('b' or 'w')
        :param probability: preferred probability to win (float, percents)
        :param log_f: function to pass logging messages to
        """
        command = "genmove {}\r\n".format(color)
        self._log("Asking LZ to {}".format(command.strip()))
        self.pass_to_lz(command)
        self._log("Waiting for LZ")

        # Ask LZ for the best move
        move = self._wait_for_move()
        self._log("LZ wanted to play {}".format(move))

        if move == "resign":
            sys.stdout.write("= resign\r\n")
            sys.stdout.flush()
            return

        if move == "pass":
            sys.stdout.write("= pass\r\n")
            sys.stdout.flush()
            return

        # Now wait for variations
        self._log("Waiting for variations")
        while True:
            line = self._lz_err.get()  # blocking!
            sys.stderr.write(line)
            sys.stderr.flush()
            if line[:8] == 'NN eval=':
                break

        self._log("Reading variations")
        variations = []
        while True:
            line = self._lz_err.get()  # blocking!
            sys.stderr.write(line)
            sys.stderr.flush()
            if line[:8] == 'NN eval=':
                # variations for expected reply start -- we're done
                break
            match = LzWrapper._VARIATION.match(line)
            if match:
                variations.append(match.groups())

        self._log("{} variations read, "
                  "choosing the most suitable".format(len(variations)))
        best = None
        current = None
        for var_move, percent in variations:
            deviation = abs(float(percent) - probability)
            if (current is None) or (deviation < current):
                best = var_move
                current = deviation
                self._log("{} looks more suitable ({}%)".format(best, current))

        self._log("Going to play {} ({}%)".format(best, current))

        # Undo the move and play the chosen one instead
        self.pass_to_lz("undo\r\n")
        self._consume_stdout_until_ready()
        self.pass_to_lz("play {} {}\r\n".format(color, best))
        self._consume_stdout_until_ready()

        # Finally, output GTP line with the move
        sys.stdout.write("= {}\r\n".format(best))
        sys.stdout.flush()


def load_config():
    """
    Load dumbstone.ini
    """
    path = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(path, 'dumbstone.ini')
    config = ConfigParser()
    with open(config_path, 'r') as config_file:
        config.read_file(config_file)
    return config


def _dumb_log(message):
    sys.stderr.write("DUMBSTONE: {}\r\n".format(message))


def main(log_f=_dumb_log):
    """
    Entry point.
    """
    config = load_config()
    lz_binary = config.get('leelaz', 'leelaz')
    weights = config.get('leelaz', 'weights')
    visits = config.get('leelaz', 'visits')
    probability = float(config.get('stupidity', 'win_percent'))

    wrapper = LzWrapper(lz_binary, weights, visits, log_f)

    stdin_q = start_reader(sys.stdin)

    count = 0
    while True:
        changed = False
        # Dump everything we have in stderr
        if wrapper.dump_stderr():
            changed = True
        # Dump everything we have in stdout
        if wrapper.dump_stdout():
            changed = True

        # Read input command
        try:
            cmd = stdin_q.get_nowait()
            changed = True
            count = 0
            log_f("Input command: {}".format(cmd))
            if cmd.strip() == 'quit':
                wrapper.pass_to_lz("{}\r\n".format(cmd))
                sys.exit(0)
            elif cmd[:8] == "genmove ":
                color = cmd[8]
                wrapper.genmove(color, probability)
            else:
                wrapper.pass_to_lz(cmd)
                wrapper.dump_stdout_until_ready()
                log_f("Command ok")
        except Empty:
            if not changed:
                count += 1
            if count > 10:
                time.sleep(1)


if __name__ == '__main__':
    main()
