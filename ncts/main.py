#!/usr/bin/env python3
import curses
import curses.textpad
import functools
import subprocess
import locale
import operator as O
import threading
from collections import OrderedDict

locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

decode = lambda b: b.decode(code)


class PeriodicTimer(object):
    def __init__(self, interval, callback, args=[], kwargs={}):
        self.interval = interval

        @functools.wraps(callback)
        def wrapper(*args, **kwargs):
            result = callback(*args, **kwargs)
            self.thread = threading.Timer(self.interval, self.callback,
                                      args=self.args, kwargs=self.kwargs)
            self.thread.start()

        self.callback = wrapper
        self.args, self.kwargs = args, kwargs

    def start(self):
        self.thread = threading.Timer(self.interval, self.callback,
                                      args=self.args, kwargs=self.kwargs)
        self.thread.start()

    def cancel(self):
        self.thread.cancel()


class TaskSpooler(object):
    command = 'tsp'
    remove_args = '-r'

    def get_command(self, command):
        return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)

    def remove_task(self, id=None):
        command = [self.command, self.remove_args]
        if id is not None:
            command.append(id)
        subprocess.call(command)

    @property
    def tasks(self):
        return self._tasks

    def order_tasks(self, key=None, reverse=False):
        if key not in ['id', 'state', 'output', 'elevel', 'times', 'command']:
            key = 'id'

        if key == 'id':
            func = lambda t: int(t[0])
        elif key == 'state':
            state_level = {'running': 1, 'queued': 2}
            getter = lambda t: O.itemgetter(key)(t[1])
            func = lambda t: state_level.get(getter(t), 10)
        else:
            func = lambda t: O.itemgetter(key)(t[1])

        self._tasks = OrderedDict(sorted(self._tasks.items(), reverse=reverse,
                                         key=func))

    def read_task_list(self):
        cmd = self.get_command([self.command])

        self._tasks = {}
        self.header = decode(next(cmd.stdout))

        for line in cmd.stdout:
            id_, task = self._parse_task(decode(line))
            self._tasks[id_] = task

        self.order_tasks('id', reverse=True)

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


class Box(object):
    def __init__(self, y=0, x=0, height=None, width=None):
        if width and height:
            self.window = curses.newwin(height, width, y, x)
        else:
            self.window = curses.newwin(y, x)
        self.y, self.x = y, x
        self.height, self.width = self.window.getmaxyx()

    def add_pad(self, height=0, width=0):
        self.pad = curses.newpad(height, width)

    def draw(self):
        box_width = max(self.width, TaskSpoolerGui.screen_width) - 1
        box_height = max(self.height, TaskSpoolerGui.screen_height)

        self.window.box()
        self.window.noutrefresh()
        self.pad.overlay(self.window)
        self.pad.noutrefresh(0, 0, self.y + 1, self.x + 1, box_height - 1, box_width - 1)

    def resize(self, new_height, new_width):
        self.height, self.width = new_height, new_width
        self.window.resize(new_height, new_width)

        height, width = self.pad.getmaxyx()
        if width < self.width:
            self.pad.resize(height, new_width)

    def move(self, y, x):
        self.y, self.x = y, x
        self.window.mvwin(y, x)


class TaskSpoolerGui(object):
    screen_width = screen_height = 0
    MAX_LINES = 500

    DOWN = 1
    UP = -1
    ESC_KEY = 27

    def __init__(self, screen):
        curses.curs_set(0)
        self.screen = screen
        self.screen.refresh()

        self.ts = TaskSpooler()

        self.create_colours()
        self.create_layout()
        self.calculate_dimensions()
        self.run()

    def __del__(self):
        self.timer.cancel()
        curses.curs_set(1)

    def run(self):
        self.timer = PeriodicTimer(0.5, self.redraw)
        self.timer.start()

        while True:
            self.redraw()

            c = self.screen.getch()
            if c == curses.KEY_UP:
                self.selected_task = self.updown(self.UP)
            elif c == curses.KEY_DOWN:
                self.selected_task = self.updown(self.DOWN)
            elif c == self.ESC_KEY:
                self.remove_highlight()
            elif c in (ord('d'), ord('D')):
                self.remove_task(self.selected_task)
            elif c in (ord('q'), ord('Q')):
                break

        self.timer.cancel()

    def updown(self, inc):
        if not self.selected_task:
            self.selected_task = 0

        return max(1, min(self.max_tasks, self.selected_task + inc))

    def redraw(self):
        self.calculate_dimensions()
        self.display_screen()
        self.display_task_output(self.selected_task)
        curses.doupdate()

    def calculate_dimensions(self):
        height, width = self.screen.getmaxyx()
        if height != self.screen_height or width != self.screen_width:
            curses.resizeterm(height, width)
        else:
            return

        self.screen_height, self.screen_width = height, width

        ts_list_height = max(5, int(0.4 * height))
        self.box_ts_list.resize(ts_list_height, self.screen_width)
        self.box_ts_list.move(1, 0)

        output_height = max(0, height - ts_list_height - 1)
        self.box_output.resize(output_height, self.screen_width)
        self.box_output.move(ts_list_height + 1, 0)

    def create_colours(self):
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

    def create_layout(self):
        self.selected_task = None
        self.box_ts_list = Box()
        self.box_ts_list.add_pad(self.MAX_LINES, 80)

        self.box_output = Box()
        self.box_output.add_pad(self.MAX_LINES, 80)

    def display_screen(self):
        self.ts.read_task_list()
        self.max_tasks = len(self.ts.tasks)

        self.box_ts_list.pad.addstr(0, 0, self.ts.header, curses.A_BOLD)

        for y, task_tuple in enumerate(self.ts.tasks.items(), 1):
            id_, task = task_tuple
            color = self.get_highlight(y, task['state'], task['elevel'])
            self.box_ts_list.pad.addstr(y, 0, task['line'], color)

        self.box_ts_list.draw()

    def display_task_output(self, task_index=None):
        self.box_output.pad.clear()

        tasks = list(self.ts.tasks.values())
        if not tasks:
            return
        if not task_index:
            task = tasks[0]
        else:
            task = tasks[task_index - 1]

        try:
            with open(task['output'], 'r') as output:
                for y, line in enumerate(output):
                    self.box_output.pad.addstr(y, 0, line)

        except IOError:
            return

        self.box_output.draw()

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

    def remove_task(self, task_index=None):
        if task_index:
            try:
                task_index = list(self.ts.tasks.keys())[task_index - 1]
            except IndexError:
                return
        self.ts.remove_task(task_index)


if __name__ == '__main__':
    curses.wrapper(TaskSpoolerGui)
