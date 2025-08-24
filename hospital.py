import sqlite3, os, csv, datetime, tkinter as tk
from tkinter import ttk, messagebox, filedialog
try:
    from fpdf import FPDF; HAS_PDF=True
except: HAS_PDF=False

DB="hospital.db"

# ---------- DB core ----------
def q(sql,p=(),fetch=None):
    with sqlite3.connect(DB) as c:
        cur=c.cursor(); cur.execute(sql,p)
        if fetch=="one": return cur.fetchone()
        if fetch=="all": return cur.fetchall()
        return cur.lastrowid if sql.strip().upper().startswith("INSERT") else None

def init_db():
    q("""CREATE TABLE IF NOT EXISTS patients(
        patient_id INTEGER PRIMARY KEY, name TEXT NOT NULL, age INTEGER, gender TEXT, phone TEXT, address TEXT, added_on TEXT)""")
    q("""CREATE TABLE IF NOT EXISTS appointments(
        appointment_id INTEGER PRIMARY KEY, patient_id INTEGER, doctor TEXT, date TEXT, time TEXT, reason TEXT,
        status TEXT DEFAULT 'Scheduled', created_on TEXT, FOREIGN KEY(patient_id) REFERENCES patients(patient_id))""")
    q("""CREATE TABLE IF NOT EXISTS medicines(
        medicine_id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT, price REAL NOT NULL, stock INTEGER DEFAULT 0)""")
    q("""CREATE TABLE IF NOT EXISTS bills(
        bill_id INTEGER PRIMARY KEY, patient_id INTEGER, total REAL, created_on TEXT)""")
    q("""CREATE TABLE IF NOT EXISTS bill_items(
        id INTEGER PRIMARY KEY, bill_id INTEGER, description TEXT, qty INTEGER, unit_price REAL, amount REAL)""")

# ---------- Small helpers ----------
now = lambda: datetime.datetime.now().isoformat()
def export_csv(rows, headers, name):
    f=filedialog.asksaveasfilename(defaultextension=".csv",initialfile=name,filetypes=[("CSV","*.csv")]); 
    if not f: return
    with open(f,"w",newline="",encoding="utf-8") as o: w=csv.writer(o); w.writerow(headers); w.writerows(rows)
    messagebox.showinfo("Exported",f"Saved {f}")

def invoice_txt(bill_id):
    b=q("SELECT bill_id,patient_id,total,created_on FROM bills WHERE bill_id=?", (bill_id,), "one"); 
    its=q("SELECT description,qty,unit_price,amount FROM bill_items WHERE bill_id=?", (bill_id,), "all")
    p=q("SELECT name,age,gender,phone,address FROM patients WHERE patient_id=?", (b[1],), "one") if b else None
    if not (b and p): return None
    lines=[ "=== Hospital Invoice ===", f"Bill ID: {b[0]}", f"Date: {b[3]}", "", "Patient:",
            f"  Name: {p[0]}", f"  Age/Gender: {p[1]} / {p[2]}", f"  Phone: {p[3]}", f"  Address: {p[4]}", "",
            f"{'Description':40} {'Qty':>3} {'Unit':>8} {'Amount':>10}" ]
    for d,qy,u,a in its: lines.append(f"{d[:40]:40} {qy:>3} {u:>8.2f} {a:>10.2f}")
    lines+=["",f"TOTAL: {b[2]:.2f}"]
    fn=os.path.join(os.getcwd(),f"invoice_{b[0]}.txt"); open(fn,"w",encoding="utf-8").write("\n".join(lines)); return fn

def invoice_pdf(bill_id):
    if not HAS_PDF: return None
    b=q("SELECT bill_id,patient_id,total,created_on FROM bills WHERE bill_id=?", (bill_id,), "one"); 
    its=q("SELECT description,qty,unit_price,amount FROM bill_items WHERE bill_id=?", (bill_id,), "all")
    p=q("SELECT name,age,gender,phone,address FROM patients WHERE patient_id=?", (b[1],), "one") if b else None
    if not (b and p): return None
    fn=os.path.join(os.getcwd(),f"invoice_{b[0]}.pdf"); pdf=FPDF(); pdf.add_page(); pdf.set_font("Arial",size=12)
    for t in ("Hospital Invoice",): pdf.cell(0,8,t,ln=1,align="C"); pdf.ln(2)
    for t in (f"Bill ID: {b[0]}",f"Date: {b[3]}", "", f"Patient: {p[0]} ({p[1]}/{p[2]})", f"Phone: {p[3]}", f"Address: {p[4]}"):
        pdf.cell(0,6,t,ln=1)
    pdf.ln(4); pdf.set_font("Arial",size=10)
    for w,t,a in ((90,"Description","L"),(20,"Qty","C"),(30,"Unit","R"),(30,"Amount","R")): pdf.cell(w,6,t,1,0,a)
    pdf.ln()
    for d,qy,u,a in its:
        for w,t,a2 in ((90,d[:45],"L"),(20,str(qy),"C"),(30,f"{u:.2f}","R"),(30,f"{a:.2f}","R")): pdf.cell(w,6,t,1,0,a2)
        pdf.ln()
    pdf.ln(3); pdf.set_font("Arial","B",12); pdf.cell(0,6,f"TOTAL: {b[2]:.2f}",ln=1); pdf.output(fn); return fn

# ---------- App ----------
class App:
    def __init__(s,root):
        s.r=root; s.r.title("Hospital Management System"); s.r.geometry("1000x640")
        nb=ttk.Notebook(s.r); nb.pack(fill="both",expand=True,padx=6,pady=6)
        s.tp, s.ta, s.tm, s.tb, s.tr = (ttk.Frame(nb) for _ in range(5))
        nb.add(s.tp,text="Patients"); nb.add(s.ta,text="Appointments"); nb.add(s.tm,text="Pharmacy"); nb.add(s.tb,text="Billing"); nb.add(s.tr,text="Reports")
        s.build_patients(); s.build_appointments(); s.build_meds(); s.build_billing(); s.build_reports()

    # ---- Patients
    def build_patients(s):
        L=ttk.Frame(s.tp); L.pack(side="left",fill="y",padx=6,pady=6)
        def e(lbl,w=28): ttk.Label(L,text=lbl).pack(anchor="w"); x=ttk.Entry(L,width=w); x.pack(); return x
        s.p_name=e("Name:"); s.p_age=e("Age:",10); ttk.Label(L,text="Gender:").pack(anchor="w")
        s.p_gender=ttk.Combobox(L,values=["Male","Female","Other"],width=26); s.p_gender.pack()
        s.p_phone=e("Phone:"); ttk.Label(L,text="Address:").pack(anchor="w"); s.p_addr=tk.Text(L,width=28,height=4); s.p_addr.pack()
        ttk.Button(L,text="Add",command=s.p_add).pack(fill="x",pady=4)
        ttk.Button(L,text="Update Selected",command=s.p_upd).pack(fill="x",pady=2)
        ttk.Button(L,text="Clear",command=lambda:(s.p_name.delete(0,"end"),s.p_age.delete(0,"end"),s.p_gender.set(""),s.p_phone.delete(0,"end"),s.p_addr.delete("1.0","end"))).pack(fill="x",pady=2)
        R=ttk.Frame(s.tp); R.pack(side="left",fill="both",expand=True,padx=6,pady=6)
        top=ttk.Frame(R); top.pack(fill="x")
        s.p_kw=tk.StringVar(); ttk.Label(top,text="Search:").pack(side="left"); ttk.Entry(top,textvariable=s.p_kw).pack(side="left"); 
        ttk.Button(top,text="Search",command=s.p_search).pack(side="left",padx=3); ttk.Button(top,text="Refresh",command=s.p_load).pack(side="left",padx=3)
        cols=("id","name","age","gender","phone","address","added_on"); s.p_tv=ttk.Treeview(R,columns=cols,show="headings",selectmode="browse")
        [s.p_tv.heading(c,text=c.title()) or s.p_tv.column(c,width=120) for c in cols]; s.p_tv.column("address",width=240); s.p_tv.pack(fill="both",expand=True)
        s.p_tv.bind("<<TreeviewSelect>>",s.p_fill); s.p_load()

    def p_add(s):
        n=s.p_name.get().strip(); 
        if not n: return messagebox.showwarning("Required","Name is required.")
        pid=q("INSERT INTO patients(name,age,gender,phone,address,added_on) VALUES(?,?,?,?,?,?)",
              (n, s.p_age.get().strip() or None, s.p_gender.get().strip(), s.p_phone.get().strip(), s.p_addr.get("1.0","end").strip(), now()))
        messagebox.showinfo("Added",f"Patient ID {pid}"); s.p_load()
    def p_load(s):
        for i in s.p_tv.get_children(): s.p_tv.delete(i)
        for r in q("SELECT patient_id,name,age,gender,phone,address,added_on FROM patients ORDER BY patient_id DESC",(),"all"): s.p_tv.insert("","end",values=r)
    def p_fill(s,_=None):
        sel=s.p_tv.selection(); 
        if not sel: return
        s.pid=s.p_tv.item(sel[0])["values"][0]; v=s.p_tv.item(sel[0])["values"]
        s.p_name.delete(0,"end"); s.p_name.insert(0,v[1])
        s.p_age.delete(0,"end"); s.p_age.insert(0,v[2]); s.p_gender.set(v[3]); s.p_phone.delete(0,"end"); s.p_phone.insert(0,v[4])
        s.p_addr.delete("1.0","end"); s.p_addr.insert("1.0",v[5])
    def p_upd(s):
        if not hasattr(s,"pid"): return messagebox.showwarning("Select","Choose a patient.")
        q("UPDATE patients SET name=?,age=?,gender=?,phone=?,address=? WHERE patient_id=?",
          (s.p_name.get().strip(), s.p_age.get().strip() or None, s.p_gender.get().strip(), s.p_phone.get().strip(), s.p_addr.get("1.0","end").strip(), s.pid))
        messagebox.showinfo("Updated","Patient updated."); s.p_load()
    def p_search(s):
        kw=f"%{s.p_kw.get().strip()}%"; rows=q("SELECT patient_id,name,age,gender,phone,address,added_on FROM patients WHERE name LIKE ? OR phone LIKE ? OR address LIKE ?",
                                              (kw,kw,kw),"all"); 
        for i in s.p_tv.get_children(): s.p_tv.delete(i)
        [s.p_tv.insert("",'end',values=r) for r in rows]

    # ---- Appointments
    def build_appointments(s):
        T=ttk.Frame(s.ta); T.pack(fill="x",padx=6,pady=6)
        lbls=("Patient ID","Doctor","Date YYYY-MM-DD","Time HH:MM","Reason"); wids=[]
        for t,w in zip(lbls,(8,14,12,8,20)):
            ttk.Label(T,text=t+":").pack(side="left"); e=ttk.Entry(T,width=w); e.pack(side="left",padx=3); wids.append(e)
        s.a_pid,s.a_doc,s.a_date,s.a_time,s.a_reason=wids
        ttk.Button(T,text="Book",command=s.a_book).pack(side="left",padx=4)
        M=ttk.Frame(s.ta); M.pack(fill="x",padx=6); ttk.Button(M,text="Refresh",command=s.a_load).pack(side="left"); ttk.Button(M,text="Cancel Selected",command=s.a_cancel).pack(side="left",padx=4)
        cols=("id","pid","patient","doctor","date","time","reason","status"); s.a_tv=ttk.Treeview(s.ta,columns=cols,show="headings")
        [s.a_tv.heading(c,text=c.title()) or s.a_tv.column(c,width=120) for c in cols]; s.a_tv.pack(fill="both",expand=True,padx=6,pady=6); s.a_load()
    def a_book(s):
        try:
            q("INSERT INTO appointments(patient_id,doctor,date,time,reason,created_on) VALUES(?,?,?,?,?,?)",
              (int(s.a_pid.get()), s.a_doc.get().strip(), s.a_date.get().strip(), s.a_time.get().strip(), s.a_reason.get().strip(), now()))
            messagebox.showinfo("Booked","Appointment created."); s.a_load()
        except Exception as e: messagebox.showerror("Error",str(e))
    def a_load(s):
        for i in s.a_tv.get_children(): s.a_tv.delete(i)
        rows=q("""SELECT a.appointment_id,a.patient_id,p.name,a.doctor,a.date,a.time,a.reason,a.status
                  FROM appointments a JOIN patients p ON a.patient_id=p.patient_id ORDER BY a.date,a.time""",(),"all")
        [s.a_tv.insert("",'end',values=r) for r in rows]
    def a_cancel(s):
        sel=s.a_tv.selection(); 
        if not sel: return messagebox.showwarning("Select","Choose an appointment.")
        aid=s.a_tv.item(sel[0])["values"][0]; q("UPDATE appointments SET status='Cancelled' WHERE appointment_id=?", (aid,))
        messagebox.showinfo("Cancelled",f"Appointment {aid} cancelled."); s.a_load()

    # ---- Pharmacy
    def build_meds(s):
        L=ttk.Frame(s.tm); L.pack(side="left",fill="y",padx=6,pady=6)
        def e(t,w=28): ttk.Label(L,text=t).pack(anchor="w"); x=ttk.Entry(L,width=w); x.pack(); return x
        s.m_name=e("Name:"); s.m_desc=e("Description:"); s.m_price=e("Price:",12); s.m_stock=e("Stock:",12)
        ttk.Button(L,text="Add",command=s.m_add).pack(fill="x",pady=4)
        ttk.Button(L,text="Update Selected",command=s.m_upd).pack(fill="x",pady=2)
        ttk.Button(L,text="Clear",command=lambda:(s.m_name.delete(0,"end"),s.m_desc.delete(0,"end"),s.m_price.delete(0,"end"),s.m_stock.delete(0,"end"))).pack(fill="x",pady=2)
        R=ttk.Frame(s.tm); R.pack(side="left",fill="both",expand=True,padx=6,pady=6)
        top=ttk.Frame(R); top.pack(fill="x"); s.m_kw=tk.StringVar()
        ttk.Label(top,text="Search:").pack(side="left"); ttk.Entry(top,textvariable=s.m_kw).pack(side="left"); 
        ttk.Button(top,text="Refresh",command=s.m_load).pack(side="left",padx=4); ttk.Button(top,text="Export CSV",command=s.m_export).pack(side="left",padx=4)
        cols=("id","name","desc","price","stock"); s.m_tv=ttk.Treeview(R,columns=cols,show="headings")
        [s.m_tv.heading(c,text=c.title()) or s.m_tv.column(c,width=140) for c in cols]; s.m_tv.pack(fill="both",expand=True)
        s.m_tv.bind("<<TreeviewSelect>>",s.m_fill); s.m_load()
    def m_add(s):
        if not s.m_name.get().strip(): return messagebox.showwarning("Required","Name needed")
        try: price=float(s.m_price.get().strip()); stock=int(s.m_stock.get().strip() or 0)
        except: return messagebox.showwarning("Invalid","Enter valid price/stock")
        q("INSERT INTO medicines(name,description,price,stock) VALUES(?,?,?,?)",(s.m_name.get().strip(), s.m_desc.get().strip(), price, stock))
        messagebox.showinfo("Added","Medicine added."); s.m_load()
    def m_load(s):
        for i in s.m_tv.get_children(): s.m_tv.delete(i)
        rows=q("SELECT medicine_id,name,description,price,stock FROM medicines ORDER BY name",(),"all")
        k=s.m_kw.get().strip().lower()
        for r in rows:
            if not k or k in str(r[1]).lower() or k in str(r[2]).lower(): s.m_tv.insert("",'end',values=r)
    def s_get_sel(s,tv): 
        sel=tv.selection(); return tv.item(sel[0])["values"] if sel else None
    def m_fill(s,_=None):
        v=s.s_get_sel(s.m_tv); 
        if not v: return
        s.mid=v[0]; s.m_name.delete(0,"end"); s.m_name.insert(0,v[1])
        s.m_desc.delete(0,"end"); s.m_desc.insert(0,v[2] or "")
        s.m_price.delete(0,"end"); s.m_price.insert(0,str(v[3])); s.m_stock.delete(0,"end"); s.m_stock.insert(0,str(v[4]))
    def m_upd(s):
        if not hasattr(s,"mid"): return messagebox.showwarning("Select","Choose a medicine.")
        try:
            q("UPDATE medicines SET name=?,description=?,price=?,stock=? WHERE medicine_id=?",
              (s.m_name.get().strip(), s.m_desc.get().strip(), float(s.m_price.get().strip()), int(s.m_stock.get().strip()), s.mid))
            messagebox.showinfo("Updated","Medicine updated."); s.m_load()
        except Exception as e: messagebox.showerror("Error",str(e))
    def m_export(s):
        export_csv(q("SELECT medicine_id,name,description,price,stock FROM medicines",(),"all"),
                   ["medicine_id","name","description","price","stock"],"medicines.csv")

    # ---- Billing
    def build_billing(s):
        T=ttk.Frame(s.tb); T.pack(fill="x",padx=6,pady=6)
        ttk.Label(T,text="Patient ID:").pack(side="left"); s.b_pid=ttk.Entry(T,width=8); s.b_pid.pack(side="left",padx=4)
        ttk.Button(T,text="Load Patient",command=s.b_load_patient).pack(side="left",padx=4)
        cols=("desc","qty","unit","amount"); s.b_tv=ttk.Treeview(s.tb,columns=cols,show="headings",height=8)
        [s.b_tv.heading(c,text=c.title()) or s.b_tv.column(c,width=180 if c=='desc' else 90) for c in cols]; s.b_tv.pack(fill="x",padx=6)
        A=ttk.Frame(s.tb); A.pack(fill="x",padx=6,pady=6)
        ttk.Label(A,text="Description:").pack(side="left"); s.bi_desc=ttk.Entry(A,width=28); s.bi_desc.pack(side="left",padx=3)
        ttk.Label(A,text="Qty:").pack(side="left"); s.bi_qty=ttk.Entry(A,width=6); s.bi_qty.pack(side="left",padx=3)
        ttk.Label(A,text="Unit:").pack(side="left"); s.bi_price=ttk.Entry(A,width=10); s.bi_price.pack(side="left",padx=3)
        ttk.Button(A,text="Add Item",command=s.b_add_item).pack(side="left",padx=4)
        ttk.Button(A,text="Remove Selected",command=lambda:(s.b_tv.delete(s.b_tv.selection()[0]) if s.b_tv.selection() else None,s.b_total())).pack(side="left",padx=4)
        B=ttk.Frame(s.tb); B.pack(fill="x",padx=6,pady=6)
        s.total=tk.StringVar(value="0.00"); ttk.Label(B,text="Total:").pack(side="left"); ttk.Label(B,textvariable=s.total,font=("",10,"bold")).pack(side="left",padx=6)
        ttk.Button(B,text="Create Bill",command=s.b_create).pack(side="left",padx=4)
        ttk.Button(B,text="Save Invoice TXT",command=s.b_save_txt).pack(side="left",padx=4)
        ttk.Button(B,text="Save Invoice PDF",command=s.b_save_pdf).pack(side="left",padx=4)
        ttk.Label(s.tb,text="Recent Bills",font=("",10,"bold")).pack(anchor="w",padx=6)
        s.b_list=ttk.Treeview(s.tb,columns=("id","pid","name","total","on"),show="headings",height=6)
        [s.b_list.heading(c,text=c.title()) or s.b_list.column(c,width=160) for c in ("id","pid","name","total","on")]; s.b_list.pack(fill="both",expand=True,padx=6,pady=4)
        ttk.Button(s.tb,text="Refresh Bills",command=s.b_load).pack(padx=6,pady=2); s.b_load()

    def b_load_patient(s):
        r=q("SELECT patient_id,name FROM patients WHERE patient_id=?", (s.b_pid.get().strip(),), "one")
        if not r: return messagebox.showerror("Not found","Invalid patient ID")
        s.cur_patient=r; messagebox.showinfo("Loaded",f"Patient: {r[1]}")

    def b_add_item(s):
        try: qty=int(s.bi_qty.get()); price=float(s.bi_price.get())
        except: return messagebox.showwarning("Invalid","Enter valid qty and price")
        d=s.bi_desc.get().strip(); 
        if not d: return messagebox.showwarning("Required","Description needed")
        s.b_tv.insert("",'end',values=(d,qty,f"{price:.2f}",f"{qty*price:.2f}"))
        [x.delete(0,"end") for x in (s.bi_desc,s.bi_qty,s.bi_price)]; s.b_total()
    def b_total(s):
        t=sum(float(s.b_tv.item(i)["values"][3]) for i in s.b_tv.get_children()); s.total.set(f"{t:.2f}")
    def b_create(s):
        if not hasattr(s,"cur_patient"): return messagebox.showwarning("Patient","Load a patient first")
        items=[ {"description":v[0],"qty":int(v[1]),"unit_price":float(v[2])} for v in (s.b_tv.item(i)["values"] for i in s.b_tv.get_children()) ]
        if not items: return messagebox.showwarning("Items","Add at least one item")
        total=sum(it["qty"]*it["unit_price"] for it in items)
        bid=q("INSERT INTO bills(patient_id,total,created_on) VALUES(?,?,?)",(s.cur_patient[0],total,now()))
        for it in items: q("INSERT INTO bill_items(bill_id,description,qty,unit_price,amount) VALUES(?,?,?,?,?)",
                           (bid,it["description"],it["qty"],it["unit_price"],it["qty"]*it["unit_price"]))
        messagebox.showinfo("Created",f"Bill {bid} created."); s.b_tv.delete(*s.b_tv.get_children()); s.b_total(); s.cur_patient=None; s.b_pid.delete(0,"end"); s.b_load()
    def b_load(s):
        for i in s.b_list.get_children(): s.b_list.delete(i)
        rows=q("""SELECT b.bill_id,b.patient_id,p.name,b.total,b.created_on
                  FROM bills b JOIN patients p ON b.patient_id=p.patient_id ORDER BY b.created_on DESC""",(),"all")
        [s.b_list.insert("",'end',values=r) for r in rows]
    def b_save_txt(s):
        sel=s.b_list.selection(); 
        if not sel: return messagebox.showwarning("Select","Choose a bill")
        fn=invoice_txt(s.b_list.item(sel[0])["values"][0]); messagebox.showinfo("Saved",f"Saved {fn}") if fn else None
    def b_save_pdf(s):
        if not HAS_PDF: return messagebox.showwarning("Missing","Install: pip install fpdf")
        sel=s.b_list.selection(); 
        if not sel: return messagebox.showwarning("Select","Choose a bill")
        fn=invoice_pdf(s.b_list.item(sel[0])["values"][0]); messagebox.showinfo("Saved",f"Saved {fn}") if fn else None

    # ---- Reports
    def build_reports(s):
        f=ttk.Frame(s.tr); f.pack(padx=8,pady=8,anchor="w")
        ttk.Button(f,text="Export Patients CSV",command=lambda:export_csv(q("SELECT patient_id,name,age,gender,phone,address,added_on FROM patients",(),"all"),
                 ["patient_id","name","age","gender","phone","address","added_on"],"patients.csv")).pack(pady=4,anchor="w")
        ttk.Button(f,text="Export Appointments CSV",command=lambda:export_csv(
            q("""SELECT a.appointment_id,a.patient_id,p.name,a.doctor,a.date,a.time,a.reason,a.status
                 FROM appointments a JOIN patients p ON a.patient_id=p.patient_id""",(),"all"),
            ["appointment_id","patient_id","patient_name","doctor","date","time","reason","status"],"appointments.csv")).pack(pady=4,anchor="w")
        ttk.Button(f,text="Export Medicines CSV",command=lambda:export_csv(
            q("SELECT medicine_id,name,description,price,stock FROM medicines",(),"all"),
            ["medicine_id","name","description","price","stock"],"medicines.csv")).pack(pady=4,anchor="w")
        ttk.Button(f,text="Export Bills CSV",command=lambda:export_csv(
            q("""SELECT b.bill_id,b.patient_id,p.name,b.total,b.created_on
                 FROM bills b JOIN patients p ON b.patient_id=p.patient_id""",(),"all"),
            ["bill_id","patient_id","patient_name","total","created_on"],"bills.csv")).pack(pady=4,anchor="w")

# ---------- Seed on first run ----------
def seed():
    if q("SELECT COUNT(*) FROM patients",(),"one")[0]: return
    q("INSERT INTO patients(name,age,gender,phone,address,added_on) VALUES(?,?,?,?,?,?)",("Ram Kumar",30,"Male","9876543210","123 MG Road",now()))
    q("INSERT INTO patients(name,age,gender,phone,address,added_on) VALUES(?,?,?,?,?,?)",("Sita Devi",28,"Female","9123456780","45 Park Lane",now()))
    q("INSERT INTO medicines(name,description,price,stock) VALUES(?,?,?,?)",("Paracetamol","500mg tablet",2.5,200))
    q("INSERT INTO medicines(name,description,price,stock) VALUES(?,?,?,?)",("Amoxicillin","250mg capsule",5.0,120))
    q("INSERT INTO appointments(patient_id,doctor,date,time,reason,created_on) VALUES(?,?,?,?,?,?)",(1,"Dr. Sharma","2025-08-15","10:00","Fever",now()))
    q("INSERT INTO appointments(patient_id,doctor,date,time,reason,created_on) VALUES(?,?,?,?,?,?)",(2,"Dr. Mehta","2025-08-16","14:00","Checkup",now()))

if __name__=="__main__":
    init_db(); seed()
    root=tk.Tk(); App(root); root.mainloop()
