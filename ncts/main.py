#!/usr/bin/env python3
import curses
import curses.textpad
import subprocess
import locale
import operator as O
from collections import OrderedDict

locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

decode = lambda b: b.decode(code)


class TaskSpooler(object):
    command = 'tsp'

    def get_command(self, command):
        return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)

    @property
    def tasks(self):
        return self._tasks

    def order_tasks(self, key=None, reverse=False):
        if key not in ['id', 'state', 'output', 'elevel', 'times', 'command']:
            key = 'id'

        if key == 'id':
            func = lambda t: t[0]
        elif key == 'state':
            state_level = {'running': 1, 'queued': 2}
            getter = lambda t: O.itemgetter(key)(t[1])
            func = lambda t: state_level.get(getter(t), 10)
        else:
            func = lambda t: O.itemgetter(key)(t[1])

        self._tasks = OrderedDict(sorted(self._tasks.items(), reverse=reverse,
                                         key=func))

    def read_task_list(self):
        cmd = self.get_command(self.command)

        self._tasks = {}
        self.header = decode(next(cmd.stdout))

        for line in cmd.stdout:
            id_, task = self._parse_task(decode(line))
            self._tasks[id_] = task

        self.order_tasks('state')

    def _parse_task(self, line):
        id_, state, output, rest = line.split(None, 3)

        if state in ('running', 'queued'):
            elevel = times = None
            command = rest.strip()
        else:
            elevel, times, command = rest.split(None, 2)

        return id_, {
            'state': state,
            'output': output,
            'elevel': elevel,
            'times': times,
            'command': command,
            'line': line
        }


class TaskSpoolerGui(object):
    MAX_LINES = 500

    DOWN = 1
    UP = -1
    ESC_KEY = 27

    def __init__(self, screen):
        self.screen = screen
        self.ts = TaskSpooler()

        self.create_layout()
        self.run()

    def run(self):
        while True:
            self.display_screen()

            c = self.screen.getch()
            if c == curses.KEY_UP:
                self.selected_task = self.updown(self.UP)
            elif c == curses.KEY_DOWN:
                self.selected_task = self.updown(self.DOWN)
            elif c == self.ESC_KEY:
                self.remove_highlight()
            elif c in (ord('q'), ord('Q')):
                break

    def updown(self, inc):
        if not self.selected_task:
            self.selected_task = 0
        nextLineNum = self.selected_task + inc

        return max(1, min(self.max_tasks, nextLineNum))

    def create_layout(self):
        # Normal
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
        # Error
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_RED)
        # Queued
        curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        # Running
        curses.init_pair(7, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_GREEN)

        self.selected_task = None
        self.tsPad = curses.newpad(self.MAX_LINES, 80)
        self.outputPad = curses.newpad(self.MAX_LINES, 120)
        self.outputPad.move(20, 0)

    def display_screen(self):
        self.ts.read_task_list()

        self.tsPad.addstr(self.ts.header, curses.A_BOLD)
        max_line = len(self.ts.header)

        for y, task_tuple in enumerate(self.ts.tasks.items(), 1):
            id_, task = task_tuple
            color = self.get_highlight(y, task['state'], task['elevel'])
            self.tsPad.addstr(y, 0, task['line'], color)
            max_line = max(max_line, len(task['line']))

        self.max_tasks = y
        self.tsPad.refresh(0, 0, 0, 0, y, max_line)

        self.display_task_output()

    def display_task_output(self):
        if not self.selected_task:
            return
        self.outputPad.clear()
        task = list(self.ts.tasks.values())[self.selected_task - 1]

        max_line = 0
        try:
            with open(task['output'], 'r') as output:
                y = 0
                for y, line in enumerate(output):
                    self.outputPad.addstr(y, 0, line)
                    max_line = max(max_line, len(line))
                self.outputPad.refresh(0, 0, 20, 0, 60, 80)
        except IOError:
            return

    def get_highlight(self, line_num, state, elevel):
        if state == 'running':
            color = 7
        elif state == 'queued':
            color = 5
        elif int(elevel) != 0:
            color = 3
        else:
            color = 1
        if line_num == self.selected_task:
            color += 1
        return curses.color_pair(color)

    def remove_highlight(self):
        self.selected_task = None

    def exit(self):
        pass


if __name__ == '__main__':
    curses.wrapper(TaskSpoolerGui)
