import threading
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
import Main as bk
import ResourceStrings as st
import logging
from contextlib import closing




class Main:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(st.program_title)

        self.frame_text = tk.Frame(self.root)
        self.frame_text.pack(side=tk.LEFT)

        self.text_output = tk.Text(self.frame_text, width=65)
        self.text_output.pack(side=tk.LEFT)
        self.text_output.insert(tk.END, st.instruction)

        self.scroll_text = tk.Scrollbar(self.frame_text, orient=tk.VERTICAL, command=self.text_output.yview)
        self.scroll_text.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_output['yscrollcommand'] = self.scroll_text.set

        self.frame_buttons = tk.Frame(self.root)
        self.frame_buttons.pack(side=tk.RIGHT, fill=tk.Y)

        self.button_open = tk.Button(self.frame_buttons, text=st.button_open, command=self.action_open)
        self.button_save = tk.Button(self.frame_buttons, text=st.button_save, command=self.action_save, state=tk.DISABLED)
        self.button_start = tk.Button(self.frame_buttons, text=st.button_start, command=self.action_start, state=tk.DISABLED)
        self.checkbox_online_var = True
        self.checkbox_online = tk.Checkbutton(self.frame_buttons, text=st.checkbox_online, command=self.action_checkbox)
        self.checkbox_online.select()
        self.button_open.pack(side=tk.TOP, fill=tk.X)
        self.button_save.pack(side=tk.TOP, fill=tk.X)
        self.button_start.pack(side=tk.TOP, fill=tk.X)
        self.checkbox_online.pack(side=tk.TOP, fill=tk.X)


        self.config = None
        self.app_list = None
        self.sleepy = None
        self.exporter = None
        self.input_location = None
        self.input_list = None
        self.thread = None

    def __scroll_handler__(self, *l):
        """Source: http://infohost.nmt.edu/~shipman/soft/tkinter/web/entry.html"""
        op, how_many = l[0], l[1]

        if op == 'scroll':
            units = l[2]
            self.text_output.xview_scroll(how_many, units)
        elif op == 'moveto':
            self.text_output.xview_moveto(how_many)

    def start(self):
        """Start the main window"""
        logging.info("Loading configuration file")
        self.text_output.insert(tk.END, "Loading configuration file...\n")
        self.config = bk.load_config_file("./config.txt")
        logging.info("Creating delay timer")
        self.text_output.insert(tk.END, "Creating delay timer...\n")
        self.sleepy = bk.Delayer(50, 1.5, 15)
        self.root.mainloop()

    def close(self):
        if self.exporter is not None:
            self.exporter.close()

    def action_checkbox(self):
        """Bound to the checkbox. Toggles the variable telling us whatever we should show the legal symbols in the output."""
        self.checkbox_online_var = not self.checkbox_online_var

    def action_open(self):
        file_types = [(st.all_file, "*.*"), (st.csv_file, "*.csv"), (st.text_file, "*.txt")]
        selection = tk.filedialog.askopenfilename(parent=self.root, title=st.title_save, filetypes=file_types)

        if selection:
            logging.info("Received input location %s", selection)
            self.input_location = selection
            self.input_list = bk.users_game_list(selection)  # Pre-loads all the list to memory, instead of using a generator so that the file could be overwritten.
            self.button_save.config(state=tk.NORMAL)


    def action_save(self):
        file_types = [(st.csv_file, "*.csv"), (st.text_file, "*.txt"), (st.all_file, "*.*")]
        selection = tk.filedialog.asksaveasfilename(parent=self.root, title=st.title_open, defaultextension=".csv", filetypes=file_types)

        if selection:
            if self.exporter is not None:
                self.exporter.close()

            logging.info("Creating an exporter to %s", selection)
            self.text_output.insert(tk.END, "Creating exporter...\n")
            self.exporter = bk.Exporter(bk.Exporter.CSVFile(selection), bk.Exporter.TextBox(self.text_output, tk.END))
            self.button_start.config(state=tk.NORMAL)



    def action_start(self):
        self.button_open.config(state=tk.DISABLED)
        self.button_save.config(state=tk.DISABLED)
        self.button_start.config(state=tk.DISABLED)
        self.thread = threading.Thread(target=self.action_start_parallel)
        self.thread.start()  # TODO handle the case where the program is terminated before the thread.

    def action_start_parallel(self):
        if self.app_list is None:
            logging.info("Loading AppList")
            self.text_output.insert(tk.END, "Loading AppList...\n\n")
            self.app_list = bk.AppList().fetch()

        for game in self.input_list:
            logging.info("Processing: %s", game.users_name)
            accessed_net = game.find_id(self.app_list, self.config, self.checkbox_online_var)
            if game.id is None:
                logging.error("Couldn't find ID for %s", game.users_name)
            else:
                accessed_net = game.fetch_card_info() or accessed_net  # Order is important here. You don't want to short-circuit the fetch.
                if not game.card_status_known:
                    logging.error("Couldn't find cards status for %s", game.users_name)

            self.exporter.write(game)

            if accessed_net:  # We go to sleep if we gone online. Regardless of "err" and our success with fetching the cards.
                self.sleepy.tick()

        self.exporter.flush()
        self.text_output.insert(tk.END, "       Finished.\n")

        self.button_open.config(state=tk.NORMAL)
        self.button_save.config(state=tk.NORMAL)
        self.button_start.config(state=tk.NORMAL)
        self.thread = None







def main():
    """Starts the GUI"""
    bk.init_log(filename="log.txt", console=True, level=logging.DEBUG)

    with closing(Main()) as window:
        window.start()

    logging.shutdown()


if __name__ == "__main__":
    main()
