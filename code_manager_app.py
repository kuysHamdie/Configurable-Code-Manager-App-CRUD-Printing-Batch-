import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from PIL import Image, ImageTk
import shutil
import os
import mysql.connector

# Import all backend logic from db_utils
import db_utils


class CodeManagerApp:
    def __init__(self, master):
        self.master = master
        master.title("Configurable Code Manager App (CRUD, Printing & Batch)")

        self.notebook = ttk.Notebook(master)
        self.notebook.pack(pady=10, padx=10, expand=True, fill="both")

        self.tab_setup = ttk.Frame(self.notebook)
        self.tab_create = ttk.Frame(self.notebook)
        self.tab_list = ttk.Frame(self.notebook)
        self.tab_crud = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_setup, text='Database Setup/Backup')
        self.notebook.add(self.tab_create, text='Create Code (Single/Batch)')
        self.notebook.add(self.tab_list, text='Manage Codes (View/Print/Export)')
        self.notebook.add(self.tab_crud, text='Edit/Delete Records')

        self.setup_tab_setup()
        self.setup_tab_create()
        self.setup_tab_list()
        self.setup_tab_crud()

        self.tkimage = None
        self.temp_tkimage = None

    # ----------------------------------------------------
    # --- SETUP TAB LAYOUT
    # ----------------------------------------------------
    def setup_tab_setup(self):
        ttk.Label(self.tab_setup, text="MySQL Database Management", font=('Arial', 14, 'bold')).pack(pady=10)

        config_frame = ttk.LabelFrame(self.tab_setup, text=" MySQL Connection Configuration ")
        config_frame.pack(pady=10, padx=20, fill='x')

        db_config = db_utils.load_config()

        self.config_entries = {}
        for i, (key, value) in enumerate(db_config.items()):
            ttk.Label(config_frame, text=f"{key.capitalize()}:").grid(row=i, column=0, padx=5, pady=2, sticky='w')
            entry = ttk.Entry(config_frame, width=30)
            entry.insert(0, value)
            entry.grid(row=i, column=1, padx=5, pady=2, sticky='w')
            self.config_entries[key] = entry

        ttk.Button(config_frame, text="Save & Test Settings", command=self.handle_save_config).grid(row=len(db_config),
                                                                                                    column=0,
                                                                                                    columnspan=2,
                                                                                                    pady=5)

        ttk.Separator(self.tab_setup, orient='horizontal').pack(fill='x', padx=20, pady=10)

        # Database creation and backup
        action_frame = ttk.Frame(self.tab_setup)
        action_frame.pack(pady=5)

        ttk.Button(action_frame,
                   text="Setup Database & Tables",
                   command=self.handle_setup_db).pack(side='left', padx=5, ipadx=10)

        ttk.Button(action_frame,
                   text="Backup Database",
                   command=self.handle_backup_db).pack(side='left', padx=5, ipadx=10)

        ttk.Separator(self.tab_setup, orient='horizontal').pack(fill='x', padx=20, pady=10)

        # --- DANGER ZONE ---
        ttk.Label(self.tab_setup, text="DANGER ZONE: Permanent Deletion", foreground='red',
                  font=('Arial', 10, 'bold')).pack(pady=5)

        ttk.Button(self.tab_setup,
                   text="🚨 Delete Database",
                   command=self.handle_delete_db,
                   style='Danger.TButton').pack(pady=5, ipadx=20)

        self.master.style = ttk.Style()
        self.master.style.configure('Danger.TButton', foreground='red', font=('Arial', 10, 'bold'))

    def handle_save_config(self):
        new_settings = {key: entry.get() for key, entry in self.config_entries.items()}
        db_utils.save_config(new_settings)

        temp_config = new_settings.copy()
        temp_config.pop('database', None)
        if not temp_config.get('password'):
            temp_config.pop('password', None)

        try:
            conn = mysql.connector.connect(**temp_config)
            conn.close()
            messagebox.showinfo("Success", "Configuration saved and connection test successful!")
        except mysql.connector.Error as err:
            messagebox.showerror("Error",
                                 f"Configuration saved, but connection test failed:\n{err}\n\nCheck your MySQL settings.")

    def handle_setup_db(self):
        db_config = db_utils.load_config()
        success, message = db_utils.setup_database_tables(db_config)
        if success:
            messagebox.showinfo("Success", message)
        else:
            messagebox.showerror("DB Setup Error", message)

    def handle_backup_db(self):
        db_config = db_utils.load_config()
        success, message = db_utils.backup_database(db_config)
        if success:
            messagebox.showinfo("Success", message)
        else:
            messagebox.showerror("Backup Error", message)

    def handle_delete_db(self):
        db_name = db_utils.load_config()['database']

        if not messagebox.askyesno("CONFIRM PERMANENT DELETION",
                                   f"WARNING: You are about to PERMANENTLY delete the database: '{db_name}'. This action cannot be undone. Are you absolutely sure?"):
            return

        if not messagebox.askyesno("FINAL CONFIRMATION",
                                   f"🚨 DOUBLE CHECK! Is the database name you want to delete correct: '{db_name}'?"):
            return

        conn = db_utils.get_db_connection(use_db_name=False)
        if not conn:
            messagebox.showerror("DB Error", "Cannot connect to MySQL server to perform deletion. Check config.")
            return

        try:
            cursor = conn.cursor()
            cursor.execute(f"DROP DATABASE `{db_name}`")
            conn.commit()

            file_msg = ""
            if os.path.exists(db_utils.CODES_DIR):
                shutil.rmtree(db_utils.CODES_DIR)
                os.makedirs(db_utils.CODES_DIR)
                file_msg = "\n(Associated local code files folder also reset.)"

            messagebox.showinfo("Success", f"Database '{db_name}' has been PERMANENTLY deleted." + file_msg)

            self.update_code_list()
            self.update_crud_list()

        except mysql.connector.Error as err:
            messagebox.showerror("DB Deletion Error", f"Failed to delete database '{db_name}': {err}")
        finally:
            if 'cursor' in locals():
                cursor.close()
            if conn:
                conn.close()

    # ----------------------------------------------------
    # --- CREATE TAB LAYOUT (MODIFIED FOR SINGLE/BATCH) ---
    # ----------------------------------------------------
    def setup_tab_create(self):
        ttk.Label(self.tab_create, text="Generate QR or Barcode", font=('Arial', 14, 'bold')).grid(row=0, column=0,
                                                                                                   columnspan=2,
                                                                                                   pady=10)

        # New: Generation Mode Selection
        ttk.Label(self.tab_create, text="Generation Mode:").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.generation_mode = tk.StringVar(value='QR_TEXT_SINGLE')

        # Grouped Radiobuttons for Type AND Mode
        ttk.Radiobutton(self.tab_create, text="Single QR Code (Text/Link)", variable=self.generation_mode,
                        value='QR_TEXT_SINGLE',
                        command=self.update_create_fields).grid(row=1, column=1, padx=5, pady=5, sticky='w')
        ttk.Radiobutton(self.tab_create, text="Single QR Code (Wi-Fi Config)", variable=self.generation_mode,
                        value='QR_WIFI_SINGLE',
                        command=self.update_create_fields).grid(row=2, column=1, padx=5, pady=5, sticky='w')
        ttk.Radiobutton(self.tab_create, text="Single Barcode (Code128)", variable=self.generation_mode,
                        value='BAR_SINGLE',
                        command=self.update_create_fields).grid(row=3, column=1, padx=5, pady=5, sticky='w')

        ttk.Radiobutton(self.tab_create, text="Batch QR Code (Numbered Sequence)", variable=self.generation_mode,
                        value='QR_BATCH',
                        command=self.update_create_fields).grid(row=4, column=1, padx=5, pady=5, sticky='w')
        ttk.Radiobutton(self.tab_create, text="Batch Barcode (Numbered Sequence)", variable=self.generation_mode,
                        value='BAR_BATCH',
                        command=self.update_create_fields).grid(row=5, column=1, padx=5, pady=5, sticky='w')

        ttk.Separator(self.tab_create, orient='horizontal').grid(row=6, column=0, columnspan=2, sticky='ew', pady=5)

        self.input_frame = ttk.Frame(self.tab_create)
        self.input_frame.grid(row=7, column=0, columnspan=2, padx=10, pady=5, sticky='ew')

        # FIX: Define the button before calling update_create_fields
        self.generate_button = ttk.Button(self.tab_create, text="Generate & Save Code",
                                          command=self.handle_generate_code_or_batch)
        self.generate_button.grid(row=8, column=0, columnspan=2, pady=10)

        self.update_create_fields()

        self.image_preview_label = ttk.Label(self.tab_create, text="Code Preview")
        self.image_preview_label.grid(row=9, column=0, columnspan=2, pady=10)

    def update_create_fields(self):
        for widget in self.input_frame.winfo_children():
            widget.destroy()

        mode = self.generation_mode.get()

        if 'SINGLE' in mode:
            # --- Single Generation Fields ---
            if mode == 'QR_TEXT_SINGLE' or mode == 'BAR_SINGLE':
                label_text = "Data / Link:" if mode == 'QR_TEXT_SINGLE' else "Barcode Data (Alphanumeric):"
                ttk.Label(self.input_frame, text=label_text).grid(row=0, column=0, padx=5, pady=5, sticky='w')
                self.data_entry = ttk.Entry(self.input_frame, width=50)
                self.data_entry.grid(row=0, column=1, padx=5, pady=5)
                row_offset = 1

            elif mode == 'QR_WIFI_SINGLE':
                ttk.Label(self.input_frame, text="Network Name (SSID):").grid(row=0, column=0, padx=5, pady=2,
                                                                              sticky='w')
                self.wifi_ssid = ttk.Entry(self.input_frame, width=30)
                self.wifi_ssid.grid(row=0, column=1, padx=5, pady=2, sticky='w')

                ttk.Label(self.input_frame, text="Password:").grid(row=1, column=0, padx=5, pady=2, sticky='w')
                self.wifi_pass = ttk.Entry(self.input_frame, width=30, show='*')
                self.wifi_pass.grid(row=1, column=1, padx=5, pady=2, sticky='w')

                ttk.Label(self.input_frame, text="Encryption Type:").grid(row=2, column=0, padx=5, pady=2, sticky='w')
                self.wifi_auth = ttk.Combobox(self.input_frame, values=['WPA/WPA2', 'WEP', 'None'], state='readonly',
                                              width=28)
                self.wifi_auth.set('WPA/WPA2')
                self.wifi_auth.grid(row=2, column=1, padx=5, pady=2, sticky='w')
                row_offset = 3

            # Common single-mode fields
            ttk.Label(self.input_frame, text="File Name:").grid(row=row_offset, column=0, padx=5, pady=5, sticky='w')
            self.filename_entry = ttk.Entry(self.input_frame, width=50)
            self.filename_entry.grid(row=row_offset, column=1, padx=5, pady=5)
            self.generate_button.config(text="Generate & Save Single Code")

        elif 'BATCH' in mode:
            # --- Batch Generation Fields (NEW) ---
            row = 0
            ttk.Label(self.input_frame, text="Code Prefix (Text):").grid(row=row, column=0, padx=5, pady=2, sticky='w')
            self.batch_prefix = ttk.Entry(self.input_frame, width=30)
            self.batch_prefix.grid(row=row, column=1, padx=5, pady=2, sticky='w')

            row += 1
            ttk.Label(self.input_frame, text="Data Suffix (Optional):").grid(row=row, column=0, padx=5, pady=2,
                                                                             sticky='w')
            self.batch_suffix = ttk.Entry(self.input_frame, width=30)
            self.batch_suffix.grid(row=row, column=1, padx=5, pady=2, sticky='w')

            row += 1
            ttk.Label(self.input_frame, text="Starting Number (From):").grid(row=row, column=0, padx=5, pady=2,
                                                                             sticky='w')
            self.batch_start = ttk.Entry(self.input_frame, width=15)
            self.batch_start.insert(0, '1')
            self.batch_start.grid(row=row, column=1, padx=5, pady=2, sticky='w')

            row += 1
            ttk.Label(self.input_frame, text="Ending Number (To):").grid(row=row, column=0, padx=5, pady=2, sticky='w')
            self.batch_end = ttk.Entry(self.input_frame, width=15)
            self.batch_end.insert(0, '10')
            self.batch_end.grid(row=row, column=1, padx=5, pady=2, sticky='w')

            row += 1
            ttk.Label(self.input_frame, text="Number Padding (Length):").grid(row=row, column=0, padx=5, pady=2,
                                                                              sticky='w')
            self.batch_padding = ttk.Entry(self.input_frame, width=15)
            self.batch_padding.insert(0, '4')
            self.batch_padding.grid(row=row, column=1, padx=5, pady=2, sticky='w')

            self.generate_button.config(text=f"Generate & Save Batch ({'QR' if mode == 'QR_BATCH' else 'BAR'})")

        self.generate_button.config(command=self.handle_generate_code_or_batch)

    def handle_generate_code_or_batch(self):
        """Dispatches to single or batch handler based on selected mode."""
        mode = self.generation_mode.get()
        if 'SINGLE' in mode:
            self.handle_generate_single_code()
        elif 'BATCH' in mode:
            self.handle_generate_batch()

    def handle_generate_single_code(self):
        """Handles single QR or Barcode generation."""
        filename = self.filename_entry.get().strip()
        mode = self.generation_mode.get()
        data = None

        if not filename:
            messagebox.showwarning("Input Error", "File Name field cannot be empty.")
            return

        if mode == 'QR_TEXT_SINGLE' or mode == 'BAR_SINGLE':
            data = self.data_entry.get().strip()
            if not data:
                messagebox.showwarning("Input Error", "Data field cannot be empty.")
                return

        elif mode == 'QR_WIFI_SINGLE':
            ssid = self.wifi_ssid.get().strip()
            password = self.wifi_pass.get().strip()
            auth = self.wifi_auth.get()
            if not ssid:
                messagebox.showwarning("Input Error", "Wi-Fi Network Name (SSID) cannot be empty.")
                return
            data = db_utils.format_wifi_payload(ssid, password, auth)

        # --- Generation Logic ---
        if 'QR' in mode:
            path = db_utils.generate_qr(data, filename)
            code_name = "QR Code"
        elif mode == 'BAR_SINGLE':
            if not data.isalnum() and not all(c in ' -$./+%' for c in data):
                messagebox.showwarning("Barcode Error",
                                       "Barcode data should primarily contain numbers and basic alphanumeric characters.")
                return
            path = db_utils.generate_barcode(data, filename)
            code_name = "Barcode"
        else:
            path = None

        if path:
            messagebox.showinfo("Success", f"{code_name} saved and recorded successfully.")
            self.show_image_preview(path)
            self.update_code_list()
            self.update_crud_list()

    def handle_generate_batch(self):
        """Handles the new batch code generation logic."""
        mode = self.generation_mode.get()
        code_type = 'QR' if mode == 'QR_BATCH' else 'BAR'

        try:
            prefix = self.batch_prefix.get().strip()
            suffix = self.batch_suffix.get().strip()
            start_num = int(self.batch_start.get().strip())
            end_num = int(self.batch_end.get().strip())
            padding = int(self.batch_padding.get().strip())

        except ValueError:
            messagebox.showerror("Input Error", "From, To, and Padding must be valid integers.")
            return

        if start_num <= 0 or end_num <= 0 or padding <= 0:
            messagebox.showerror("Input Error", "All numbers (From, To, Padding) must be greater than zero.")
            return

        if end_num < start_num:
            messagebox.showerror("Input Error", "The 'To' number must be greater than or equal to the 'From' number.")
            return

        total_count = end_num - start_num + 1

        if total_count > 500:
            if not messagebox.askyesno("Confirm Large Batch",
                                       f"You are about to generate {total_count} codes. This may take time. Proceed?"):
                return

        # Call the utility function
        generated_count, errors = db_utils.generate_batch_codes(
            code_type, prefix, start_num, end_num, padding, suffix
        )

        if errors:
            error_msg = "\n".join(errors[:5])  # Show first 5 errors
            messagebox.showwarning("Batch Finished with Errors",
                                   f"{generated_count} codes generated successfully out of {total_count}.\n"
                                   f"First few errors:\n{error_msg}")
        else:
            messagebox.showinfo("Batch Generation Success",
                                f"Successfully generated and saved {generated_count} {code_type} codes.")

        self.update_code_list()
        self.update_crud_list()

    def show_image_preview(self, path):
        try:
            img = Image.open(path)
            img = img.resize((200, 200), Image.LANCZOS)
            self.tkimage = ImageTk.PhotoImage(img)
            self.image_preview_label.config(image=self.tkimage, text="")
        except Exception:
            self.image_preview_label.config(image=None, text="Error loading image.")

    # ----------------------------------------------------
    # --- LIST/MANAGE TAB LAYOUT (VIEW/PRINT/EXPORT) ---
    # ----------------------------------------------------
    def setup_tab_list(self):
        ttk.Label(self.tab_list, text="List of Created Codes", font=('Arial', 14, 'bold')).pack(pady=10)

        self.tree = ttk.Treeview(self.tab_list, columns=("ID", "Type", "Data", "Date Created", "Path"), show='headings')
        self.tree.heading("ID", text="ID")
        self.tree.heading("Type", text="Type")
        self.tree.heading("Data", text="Data")
        self.tree.heading("Date Created", text="Date Created")
        self.tree.heading("Path", text="File Path (Hidden)", anchor='w')

        self.tree.column("ID", width=50, anchor='center')
        self.tree.column("Type", width=70, anchor='center')
        self.tree.column("Data", width=300)
        self.tree.column("Date Created", width=150)
        self.tree.column("Path", width=0, stretch=tk.NO)

        self.tree.pack(fill='both', expand=True, padx=10)

        # --- Printer Selection and Action Frame ---
        print_frame = ttk.LabelFrame(self.tab_list, text=" Actions on Selected Code ")
        print_frame.pack(pady=10, padx=10, fill='x')

        printers = db_utils.get_installed_printers()
        self.printer_var = tk.StringVar(value=printers[0] if printers else "No Printers Found")

        ttk.Label(print_frame, text="Select Printer:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.printer_combo = ttk.Combobox(print_frame, textvariable=self.printer_var, values=printers, state='readonly',
                                          width=30)
        self.printer_combo.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        action_row = 1
        ttk.Button(print_frame, text="Refresh List", command=self.update_code_list).grid(row=action_row, column=0,
                                                                                         padx=5, pady=5, sticky='ew')
        ttk.Button(print_frame, text="View Code Image", command=self.handle_view_image).grid(row=action_row, column=1,
                                                                                             padx=5, pady=5,
                                                                                             sticky='ew')

        print_row = 2
        ttk.Button(print_frame, text="Export Code Image", command=self.handle_export_image).grid(row=print_row,
                                                                                                 column=0, padx=5,
                                                                                                 pady=5, sticky='ew')
        ttk.Button(print_frame,
                   text="Print Selected Code",
                   command=self.handle_print_selected_code).grid(row=print_row, column=1, padx=5, pady=5, sticky='ew')

        self.update_code_list()

    def update_code_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        conn = db_utils.get_db_connection()
        if conn:
            cursor = conn.cursor()
            sql = "SELECT id, type, data, date_created, image_path FROM created_codes ORDER BY date_created DESC"
            try:
                cursor.execute(sql)
                records = cursor.fetchall()

                for rec in records:
                    date_str = rec[3].strftime("%Y-%m-%d %H:%M:%S")
                    self.tree.insert('', 'end', values=(rec[0], rec[1], rec[2], date_str, rec[4]))

            except mysql.connector.Error as err:
                messagebox.showerror("DB Error", f"Failed to load records: {err}")
            finally:
                cursor.close()
                conn.close()

    def handle_view_image(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select a code from the list to view its image.")
            return

        item_values = self.tree.item(selected_item, 'values')
        image_path = item_values[4]

        if os.path.exists(image_path):
            try:
                img_window = tk.Toplevel(self.master)
                img_window.title(f"Code Image: ID {item_values[0]}")

                img = Image.open(image_path)
                img = img.resize((300, 300), Image.LANCZOS)

                self.temp_tkimage = ImageTk.PhotoImage(img)

                ttk.Label(img_window, image=self.temp_tkimage).pack(padx=10, pady=10)
                ttk.Label(img_window, text=f"Data: {item_values[2]}", font=('Arial', 10, 'bold')).pack(pady=5)
                ttk.Label(img_window, text=f"Type: {item_values[1]}").pack(pady=2)

            except Exception as e:
                messagebox.showerror("Image Load Error", f"Failed to load image from disk:\n{e}")
        else:
            messagebox.showerror("File Error", f"Image file not found at path:\n{image_path}")

    def handle_export_image(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select a code from the list to export its image.")
            return

        item_values = self.tree.item(selected_item, 'values')
        source_path = item_values[4]

        if not os.path.exists(source_path):
            messagebox.showerror("File Error", f"Image file not found at path:\n{source_path}")
            return

        original_filename = os.path.basename(source_path)
        name, ext = os.path.splitext(original_filename)

        suggested_name = f"Code_{item_values[0]}_{name}"

        save_path = filedialog.asksaveasfilename(
            defaultextension=ext,
            initialfile=suggested_name,
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            title="Export Code Image As"
        )

        if save_path:
            try:
                shutil.copyfile(source_path, save_path)
                messagebox.showinfo("Export Success", f"Image successfully exported to:\n{save_path}")
            except Exception as e:
                messagebox.showerror("Export Failed", f"Could not export file:\n{e}")

    def handle_print_selected_code(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select a code from the list to print.")
            return

        item_values = self.tree.item(selected_item, 'values')
        image_path = item_values[4]
        printer_name = self.printer_var.get()

        if not os.path.exists(image_path):
            messagebox.showerror("File Error", f"Image file not found at path:\n{image_path}")
            return

        if not printer_name or printer_name == "No Printers Found":
            messagebox.showwarning("Printer Error",
                                   "No printer is selected or detected. Please check your system settings.")
            return

        success, message = db_utils.print_file_os(image_path, printer_name)

        if success:
            messagebox.showinfo("Printing Success", f"Successfully sent file to printer.\n{message}")
        else:
            messagebox.showerror("Printing Failed",
                                 f"Could not initiate printing. Please check permissions and the selected printer.\nError Details: {message}")

    # ----------------------------------------------------
    # --- CRUD TAB LAYOUT (UPDATE/DELETE) ---
    # ----------------------------------------------------
    def setup_tab_crud(self):
        ttk.Label(self.tab_crud, text="Edit or Delete Existing Codes", font=('Arial', 14, 'bold')).pack(pady=10)

        self.crud_tree = ttk.Treeview(self.tab_crud, columns=("ID", "Type", "Data", "Date Created", "Path"),
                                      show='headings')
        self.crud_tree.heading("ID", text="ID")
        self.crud_tree.heading("Type", text="Type")
        self.crud_tree.heading("Data", text="Data")
        self.crud_tree.heading("Date Created", text="Date Created")
        self.crud_tree.column("ID", width=50, anchor='center')
        self.crud_tree.column("Type", width=70, anchor='center')
        self.crud_tree.column("Data", width=250)
        self.crud_tree.column("Date Created", width=150)
        self.crud_tree.column("Path", width=0, stretch=tk.NO)

        self.crud_tree.pack(fill='x', padx=10)
        self.crud_tree.bind('<<TreeviewSelect>>', self.load_selected_record)

        ttk.Button(self.tab_crud, text="Refresh Records", command=self.update_crud_list).pack(pady=5)

        ttk.Separator(self.tab_crud, orient='horizontal').pack(fill='x', padx=20, pady=10)

        edit_frame = ttk.LabelFrame(self.tab_crud, text=" Selected Record Details (Update) ")
        edit_frame.pack(pady=5, padx=20, fill='x')

        ttk.Label(edit_frame, text="Record ID:").grid(row=0, column=0, padx=5, pady=2, sticky='w')
        self.crud_id = ttk.Label(edit_frame, text="", font=('Arial', 10, 'bold'))
        self.crud_id.grid(row=0, column=1, padx=5, pady=2, sticky='w')

        ttk.Label(edit_frame, text="Code Type:").grid(row=1, column=0, padx=5, pady=2, sticky='w')
        self.crud_type = ttk.Label(edit_frame, text="")
        self.crud_type.grid(row=1, column=1, padx=5, pady=2, sticky='w')

        ttk.Label(edit_frame, text="New Data:").grid(row=2, column=0, padx=5, pady=2, sticky='w')
        self.crud_data_entry = ttk.Entry(edit_frame, width=50)
        self.crud_data_entry.grid(row=2, column=1, padx=5, pady=2, sticky='w')

        action_frame = ttk.Frame(self.tab_crud)
        action_frame.pack(pady=10)

        ttk.Button(action_frame, text="Update Record Data", command=self.handle_update_record).pack(side='left',
                                                                                                    padx=10, ipadx=10)
        ttk.Button(action_frame, text="Delete Record", command=self.handle_delete_record).pack(side='left', padx=10,
                                                                                               ipadx=10)

        self.update_crud_list()

    def update_crud_list(self):
        for item in self.crud_tree.get_children():
            self.crud_tree.delete(item)

        conn = db_utils.get_db_connection()
        if conn:
            cursor = conn.cursor()
            sql = "SELECT id, type, data, date_created, image_path FROM created_codes ORDER BY id DESC"
            try:
                cursor.execute(sql)
                records = cursor.fetchall()

                for rec in records:
                    date_str = rec[3].strftime("%Y-%m-%d %H:%M:%S")
                    self.crud_tree.insert('', 'end', values=(rec[0], rec[1], rec[2], date_str, rec[4]))

            except mysql.connector.Error as err:
                messagebox.showerror("DB Error", f"Failed to load records for CRUD: {err}")
            finally:
                cursor.close()
                conn.close()

        self.update_code_list()

    def load_selected_record(self, event):
        selected_item = self.crud_tree.focus()
        if not selected_item:
            return

        values = self.crud_tree.item(selected_item, 'values')

        self.crud_id.config(text=values[0])
        self.crud_type.config(text=values[1])

        self.crud_data_entry.delete(0, tk.END)
        self.crud_data_entry.insert(0, values[2])

    def handle_update_record(self):
        record_id = self.crud_id.cget("text")
        code_type = self.crud_type.cget("text")
        new_data = self.crud_data_entry.get().strip()

        if not record_id:
            messagebox.showwarning("Input Error", "Please select a record using the list above.")
            return

        if not new_data:
            messagebox.showwarning("Input Error", "New Data field cannot be empty.")
            return

        selected_item = self.crud_tree.focus()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please re-select a record to perform the update.")
            return

        item_values = self.crud_tree.item(selected_item, 'values')
        old_path = item_values[4]

        if code_type == 'BAR':
            if not new_data.isalnum() and not all(c in ' -$./+%' for c in new_data):
                messagebox.showwarning("Barcode Error",
                                       "Barcode data should primarily contain numbers and basic alphanumeric characters.")
                return

        success, result_msg = db_utils.update_code_and_regenerate(record_id, code_type, new_data, old_path)

        if success:
            messagebox.showinfo("Success", f"Record ID {record_id} updated and image regenerated successfully!")
            self.update_crud_list()
        else:
            messagebox.showerror("Update Failed", f"Update failed. Error: {result_msg}")

    def handle_delete_record(self):
        record_id = self.crud_id.cget("text")

        if not record_id:
            messagebox.showwarning("Input Error", "Please select a record to delete.")
            return

        if not messagebox.askyesno("Confirm Delete",
                                   f"Are you sure you want to permanently delete Record ID {record_id}?"):
            return

        selected_item = self.crud_tree.focus()
        image_path = self.crud_tree.item(selected_item, 'values')[4] if selected_item else None

        conn = db_utils.get_db_connection()
        if conn:
            cursor = conn.cursor()
            sql = "DELETE FROM created_codes WHERE id = %s"
            try:
                cursor.execute(sql, (record_id,))
                conn.commit()

                file_msg = ""
                if image_path and os.path.exists(image_path):
                    os.remove(image_path)
                    file_msg = "\n(Associated file deleted.)"

                messagebox.showinfo("Success", f"Record ID {record_id} deleted successfully!" + file_msg)
                self.update_crud_list()
                self.crud_id.config(text="")
                self.crud_type.config(text="")
                self.crud_data_entry.delete(0, tk.END)

            except mysql.connector.Error as err:
                messagebox.showerror("DB Error", f"Failed to delete record: {err}")
            finally:
                cursor.close()
                conn.close()


if __name__ == '__main__':
    root = tk.Tk()
    app = CodeManagerApp(root)
    root.mainloop()