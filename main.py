import json
import os
import sqlite3
import time
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Baza de date SQLite",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = {
    "Query SQL": "query",
    "Structura bazei de date": "schema",
    "Date tabele": "tables",
    "KPI": "kpi",
}

PAGE_IDS = list(PAGES.values())
PAGE_LABELS = list(PAGES.keys())


APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "magazin.db")
KPI_TIMINGS_PATH = os.path.join(APP_DIR, "kpi_timings.json")


def load_kpi_log():
    """Încarcă log-ul de timpi KPI din fișier local."""
    if os.path.isfile(KPI_TIMINGS_PATH):
        try:
            with open(KPI_TIMINGS_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_kpi_log(log: list):
    """Salvează log-ul de timpi KPI în fișier local."""
    try:
        with open(KPI_TIMINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def init_session_state():
    if "current_page" not in st.session_state:
        st.session_state.current_page = "query"
    if "kpi_log" not in st.session_state:
        st.session_state.kpi_log = load_kpi_log()


def render_sidebar():
    """Meniu în bara laterală stânga."""
    st.sidebar.title("🗄️ Meniu")
    st.sidebar.markdown("---")

    idx = PAGE_IDS.index(st.session_state.current_page) if st.session_state.current_page in PAGE_IDS else 0
    selected = st.sidebar.radio(
        "Alege pagina",
        PAGE_LABELS,
        index=idx,
    )
    st.session_state.current_page = PAGES[selected]


def render_navbar():
    """Navbar în centru (deasupra conținutului)."""
    cols = st.columns(len(PAGE_LABELS))
    for i, label in enumerate(PAGE_LABELS):
        with cols[i]:
            page_id = PAGES[label]
            is_active = st.session_state.current_page == page_id
            btn_label = f"▶ {label}" if is_active else label
            if st.button(btn_label, key=f"nav_{page_id}", use_container_width=True):
                st.session_state.current_page = page_id
                st.rerun()


def page_query():
    """Pagina 1: Input SQL și executare."""
    st.header("🔍 Executare comenzi SQL")
    st.caption("Scrie orice comandă SQLite și apasă butonul „Execută”")

    with st.form("sql_form", clear_on_submit=False):
        query = st.text_area(
            "Comandă SQL",
            height=120,
            placeholder="Ex: SELECT * FROM nume_tabel;",
        )
        col1, col2, _ = st.columns([1, 1, 4])
        with col1:
            run = st.form_submit_button("Execută")
        with col2:
            clear = st.form_submit_button("Șterge")

    if clear:
        st.rerun()

    if run and query and query.strip():
        if not os.path.isfile(DB_PATH):
            st.error(f"Nu am găsit fișierul bazei de date: `{DB_PATH}` (în același folder cu `main.py`).")
            return

        try:
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute(query.strip())

                if query.strip().upper().startswith("SELECT"):
                    rows = cur.fetchall()
                    if rows:
                        cols = [d[0] for d in cur.description]
                        df = pd.DataFrame(rows, columns=cols)
                        st.dataframe(df, use_container_width=True)
                        st.success(f"Au fost returnate {len(rows)} rânduri.")
                    else:
                        st.info("Query-ul nu a returnat niciun rând.")
                else:
                    st.success("Comanda a fost executată cu succes.")
        except Exception as e:
            st.error(f"Eroare: {e}")


def get_tables(conn):
    """Listează tabelele din baza de date."""
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [r[0] for r in cur.fetchall()]


def get_pk_columns(conn, table: str) -> list[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info([{table}])")
    rows = cur.fetchall()
    pk = [(r[5], r[1]) for r in rows if r[5]]
    pk.sort(key=lambda x: x[0])
    return [name for _, name in pk]


FK_CONFIG: dict[tuple[str, str], tuple[str, str, str]] = {
    ("Produse", "id_categorie"): ("Categorii", "id_categorie", "denumire"),
    ("Produse", "id_furnizor"): ("Furnizori", "id_furnizor", "nume"),
    ("Comenzi", "id_produs"): ("Produse", "id_produs", "denumire"),
    ("Comenzi", "id_client"): ("Clienti", "id_client", "nume"),
    ("Categorii", "id_categorie"): ("Categorii", "id_categorie", "denumire"),
    ("Clienti", "id_client"): ("Clienti", "id_client", "nume"),
    ("Furnizori", "id_furnizor"): ("Furnizori", "id_furnizor", "nume"),
    ("Produse", "id_produs"): ("Produse", "id_produs", "denumire"),
}


def render_table_with_border(df: pd.DataFrame):
    """Afișează un DataFrame cu border la tabel."""
    if df.empty:
        st.dataframe(df, use_container_width=True)
        return

    styler = df.style.set_table_styles(
        [
            {
                "selector": "table",
                "props": "border-collapse: collapse; border: 1px solid black;",
            },
            {"selector": "th", "props": "border: 1px solid black;"},
            {"selector": "td", "props": "border: 1px solid black;"},
        ]
    )
    st.dataframe(styler, use_container_width=True)


def page_schema():
    """Pagina 2: Structura bazei de date."""
    st.header("📋 Structura bazei de date")

    if not os.path.isfile(DB_PATH):
        st.error(f"Nu am găsit fișierul bazei de date: `{DB_PATH}` (în același folder cu `main.py`).")
        return

    try:
        with sqlite3.connect(DB_PATH) as conn:
            tables = get_tables(conn)
            if not tables:
                st.info("Baza de date nu conține tabele.")
                return

            options = ["Toate tabelele"] + tables
            selected = st.selectbox(
                "Alege un tabel",
                options,
                key="schema_table_selector",
            )

            def render_table_schema(table: str):
                cur = conn.cursor()
                cur.execute(f"PRAGMA table_info({table})")
                info = cur.fetchall()
                df = pd.DataFrame(
                    info,
                    columns=["ID coloană", "Nume coloană", "Tip", "NOT NULL", "Valoare implicită", "PK"],
                )
                st.dataframe(df, use_container_width=True, hide_index=True)

            if selected == "Toate tabelele":
                for table in tables:
                    st.subheader(f"Tabel: `{table}`")
                    render_table_schema(table)
                    st.markdown("---")
            else:
                st.subheader(f"Tabel: `{selected}`")
                render_table_schema(selected)
    except Exception as e:
        st.error(f"Eroare: {e}")


def page_tables():
    """Pagina 3: Date din tabele (dropdown + toate)."""
    st.header("Date din tabele")

    if not os.path.isfile(DB_PATH):
        st.error(f"Nu am găsit fișierul bazei de date: `{DB_PATH}` (în același folder cu `main.py`).")
        return

    try:
        with sqlite3.connect(DB_PATH) as conn:
            tables = get_tables(conn)
            if not tables:
                st.info("Baza de date nu conține tabele.")
                return

            options = ["Toate tabelele"] + tables
            selected = st.selectbox(
                "Alege un tabel",
                options,
                key="table_selector",
            )

            if selected == "Toate tabelele":
                for table in tables:
                    st.subheader(f"Tabel: `{table}`")
                    df = pd.read_sql_query(f"SELECT * FROM [{table}]", conn)
                    st.dataframe(df, use_container_width=True)
                    st.markdown("---")
            else:
                st.subheader(f"Tabel: `{selected}`")

                pk_cols = get_pk_columns(conn, selected)
                has_pk = len(pk_cols) > 0

                if has_pk:
                    query = f"SELECT * FROM [{selected}]"
                else:
                    query = f"SELECT rowid as __rowid__, * FROM [{selected}]"

                df = pd.read_sql_query(query, conn)
                if df.empty:
                    st.info("Tabelul nu are rânduri.")
                    return

                key_cols = pk_cols if has_pk else ["__rowid__"]

                filtered_df = df
                with st.expander("Filtrare date în acest tabel (opțional)", expanded=False):
                    col_filter = st.selectbox("Coloană pentru filtru", df.columns, key=f"filter_col_{selected}")
                    unique_vals = sorted(df[col_filter].dropna().unique().tolist())
                    if unique_vals:
                        val_filter = st.selectbox(
                            "Valoare",
                            unique_vals,
                            key=f"filter_val_{selected}",
                        )
                        if st.button("Aplică filtru", key=f"apply_filter_{selected}"):
                            st.session_state[f"filter_applied_{selected}"] = {
                                "col": col_filter,
                                "val": val_filter,
                            }
                    else:
                        st.info("Coloana selectată nu are valori pentru filtrare.")

                filter_state = st.session_state.get(f"filter_applied_{selected}")
                if filter_state:
                    filtered_df = df[df[filter_state["col"]] == filter_state["val"]]
                    st.caption(f"{len(filtered_df)} rânduri după filtrare.")

                display_df = filtered_df
                if display_df.empty:
                    st.info("Nu există rânduri pentru filtrul selectat.")
                    return

                st.caption("Fiecare rând are valorile afișate, cu butoane „Editează” și „Șterge” în dreapta.")

                cur = conn.cursor()

                header_cols = st.columns(len(display_df.columns) + 2)
                for i, col_name in enumerate(display_df.columns):
                    header_cols[i].markdown(f"**{col_name}**")
                header_cols[-2].markdown("**Editează**")
                header_cols[-1].markdown("**Șterge**")

                for idx, row in display_df.iterrows():
                    cols = st.columns(len(display_df.columns) + 2)

                    for i, col_name in enumerate(display_df.columns):
                        val = row[col_name]
                        if pd.isna(val):
                            val = ""
                        cols[i].write(val)

                    key_vals = {c: row[c] for c in key_cols}

                    with cols[-2]:
                        edit_clicked = st.button("Editează", key=f"edit_{selected}_{idx}")
                    with cols[-1]:
                        delete_clicked = st.button("Șterge", key=f"delete_{selected}_{idx}")

                    if delete_clicked:
                        where = " AND ".join([f"[{c}] = ?" for c in key_cols])
                        sql = f"DELETE FROM [{selected}] WHERE {where}"
                        params = [key_vals[c] for c in key_cols]
                        cur.execute(sql, params)
                        conn.commit()
                        st.success("Rând șters.")
                        st.rerun()

                    if edit_clicked:
                        st.session_state["edit_target"] = {
                            "table": selected,
                            "keys": key_vals,
                        }
                        st.rerun()

                target = st.session_state.get("edit_target")
                if target and target.get("table") == selected:
                    st.markdown("---")
                    st.subheader("Editează rândul selectat")

                    where = " AND ".join([f"[{c}] = ?" for c in key_cols])
                    sql = f"SELECT * FROM [{selected}] WHERE {where}"
                    params = [target["keys"][c] for c in key_cols]
                    row_df = pd.read_sql_query(sql, conn, params=params)
                    if row_df.empty:
                        st.warning("Rândul nu mai există.")
                    else:
                        row = row_df.iloc[0]
                        non_key_cols = [c for c in row_df.columns if c not in key_cols]

                        fk_meta: dict[str, dict[str, object]] = {}
                        for col_name in row_df.columns:
                            cfg = FK_CONFIG.get((selected, col_name))
                            if not cfg:
                                continue
                            ref_table, ref_pk, ref_label = cfg
                            ref_df = pd.read_sql_query(
                                f"SELECT {ref_pk} AS id, {ref_label} AS label FROM [{ref_table}] ORDER BY label",
                                conn,
                            )
                            if ref_df.empty:
                                continue
                            fk_meta[col_name] = {
                                "ids": ref_df["id"].tolist(),
                                "labels": ref_df["label"].tolist(),
                            }

                        with st.form("edit_row_form"):
                            new_values = {}
                            new_keys = {}
                            for col_name in row_df.columns:
                                val = row[col_name]
                                if pd.isna(val):
                                    val = ""

                                if col_name in fk_meta:
                                    data = fk_meta[col_name]
                                    ids = data["ids"]
                                    labels = data["labels"]
                                    current_id = row[col_name]
                                    try:
                                        current_id_int = int(current_id)
                                    except (TypeError, ValueError):
                                        current_id_int = None
                                    if current_id_int in ids:
                                        idx_current = ids.index(current_id_int)
                                    else:
                                        idx_current = 0

                                    index = st.selectbox(
                                        col_name,
                                        list(range(len(ids))),
                                        index=idx_current,
                                        format_func=lambda i, labels=labels: str(labels[i]),
                                    )
                                    chosen_id = ids[index]
                                    if col_name in key_cols:
                                        new_keys[col_name] = chosen_id
                                    else:
                                        new_values[col_name] = chosen_id
                                else:
                                    text_val = str(val)
                                    if col_name in key_cols:
                                        new_keys[col_name] = st.text_input(
                                            col_name,
                                            value=text_val,
                                        )
                                    else:
                                        new_values[col_name] = st.text_input(
                                            col_name,
                                            value=text_val,
                                        )

                            save = st.form_submit_button("Salvează modificările")

                        if save:
                            updates = []
                            params = []

                            for c, new_val in new_values.items():
                                old_val = row[c]
                                old_str = "" if pd.isna(old_val) else str(old_val)
                                if str(new_val) == old_str:
                                    continue
                                updates.append(f"[{c}] = ?")
                                params.append(None if new_val == "" else new_val)

                            for c in key_cols:
                                new_val = new_keys.get(c, "")
                                old_val = row[c]
                                old_str = "" if pd.isna(old_val) else str(old_val)
                                if str(new_val) == old_str:
                                    continue
                                updates.append(f"[{c}] = ?")
                                params.append(None if new_val == "" else new_val)

                            if not updates:
                                st.info("Nu ai modificat nimic pe acest rând.")
                            else:
                                where = " AND ".join([f"[{c}] = ?" for c in key_cols])
                                sql = f"UPDATE [{selected}] SET {', '.join(updates)} WHERE {where}"
                                params.extend([target["keys"][c] for c in key_cols])
                                cur.execute(sql, params)
                                conn.commit()
                                st.success("Rând actualizat.")
                                del st.session_state["edit_target"]
                                st.rerun()

                st.markdown("---")
                st.subheader("Adaugă rând nou")

                cur.execute(f"PRAGMA table_info([{selected}])")
                col_info = cur.fetchall()

                auto_pk_cols = set()
                for col_item in col_info:
                    cid, col_name, col_type, notnull, dflt_value, is_pk = col_item
                    if is_pk:
                        if col_type.upper() == "INTEGER" and dflt_value is None:
                            auto_pk_cols.add(col_name)

                fk_meta_add: dict[str, dict[str, object]] = {}
                for col_item in col_info:
                    cid, col_name, col_type, notnull, dflt_value, is_pk = col_item
                    cfg = FK_CONFIG.get((selected, col_name))
                    if not cfg:
                        continue
                    ref_table, ref_pk, ref_label = cfg
                    ref_df = pd.read_sql_query(
                        f"SELECT {ref_pk} AS id, {ref_label} AS label FROM [{ref_table}] ORDER BY label",
                        conn,
                    )
                    if ref_df.empty:
                        continue
                    fk_meta_add[col_name] = {
                        "ids": ref_df["id"].tolist(),
                        "labels": ref_df["label"].tolist(),
                    }

                with st.form("add_row_form"):
                    new_row_data = {}

                    for col_item in col_info:
                        cid, col_name, col_type, notnull, dflt_value, is_pk = col_item

                        if col_name in auto_pk_cols:
                            continue

                        if col_name in fk_meta_add:
                            data = fk_meta_add[col_name]
                            ids = data["ids"]
                            labels = data["labels"]
                            if ids:
                                index = st.selectbox(
                                    col_name,
                                    list(range(len(ids))),
                                    format_func=lambda i, labels=labels: str(labels[i]),
                                    key=f"add_{col_name}",
                                )
                                new_row_data[col_name] = ids[index]
                        else:
                            val = st.text_input(
                                col_name,
                                value="",
                                key=f"add_{col_name}",
                            )
                            new_row_data[col_name] = val

                    add_row = st.form_submit_button("Adaugă rând")

                if add_row:
                    cols_to_insert = list(new_row_data.keys())
                    placeholders = ", ".join(["?" for _ in cols_to_insert])
                    cols_str = ", ".join([f"[{c}]" for c in cols_to_insert])
                    sql_insert = f"INSERT INTO [{selected}] ({cols_str}) VALUES ({placeholders})"

                    values_to_insert = []
                    for col_name in cols_to_insert:
                        val = new_row_data[col_name]
                        if val == "":
                            values_to_insert.append(None)
                        else:
                            values_to_insert.append(val)

                    try:
                        cur.execute(sql_insert, values_to_insert)
                        conn.commit()
                        st.success("Rând adăugat cu succes!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Eroare la inserare: {e}")
    except Exception as e:
        st.error(f"Eroare: {e}")


def get_kpi_sql(kpi_id: int, use_join: bool, extra: dict | None = None) -> tuple[str | None, list]:
    """Returnează (sql, params) pentru afișare sau execuție. params = [] sau [client_id] pentru KPI 5."""
    extra = extra or {}

    if kpi_id == 1:
        if not use_join:
            return (
                "SELECT id_produs, denumire, stoc "
                "FROM Produse "
                "WHERE stoc < 30 "
                "ORDER BY stoc ASC",
                [],
            )
        return (
            "SELECT p.id_produs, p.denumire AS produs, c.denumire AS categorie, p.stoc "
            "FROM Produse p "
            "JOIN Categorii c ON p.id_categorie = c.id_categorie "
            "WHERE p.stoc < 30 "
            "ORDER BY p.stoc ASC",
            [],
        )
    if kpi_id == 2:
        if not use_join:
            return (
                "SELECT p.id_categorie, SUM(c.total) AS total_vanzari FROM Comenzi c "
                "JOIN Produse p ON c.id_produs = p.id_produs GROUP BY p.id_categorie ORDER BY p.id_categorie",
                [],
            )
        return (
            "SELECT cat.denumire AS categorie, SUM(c.total) AS total_vanzari FROM Comenzi c "
            "JOIN Produse p ON c.id_produs = p.id_produs JOIN Categorii cat ON p.id_categorie = cat.id_categorie "
            "GROUP BY cat.id_categorie, cat.denumire ORDER BY total_vanzari DESC",
            [],
        )
    if kpi_id == 3:
        if not use_join:
            return (
                "SELECT COUNT(*) AS nr_produse_vanzari_mici FROM ("
                "SELECT id_produs, SUM(cantitate) AS total_bucati FROM Comenzi "
                "GROUP BY id_produs HAVING total_bucati < 5) t",
                [],
            )
        return (
            "SELECT p.denumire AS produs, SUM(c.cantitate) AS total_bucati FROM Comenzi c "
            "JOIN Produse p ON c.id_produs = p.id_produs GROUP BY p.id_produs, p.denumire "
            "HAVING SUM(c.cantitate) < 5 ORDER BY total_bucati",
            [],
        )
    if kpi_id == 4:
        if not use_join:
            return (
                "SELECT id_client, SUM(total) AS total_cheltuit FROM Comenzi "
                "GROUP BY id_client ORDER BY total_cheltuit DESC",
                [],
            )
        return (
            "SELECT cl.nume AS client, SUM(c.total) AS total_cheltuit FROM Comenzi c "
            "JOIN Clienti cl ON c.id_client = cl.id_client GROUP BY cl.id_client, cl.nume ORDER BY total_cheltuit DESC",
            [],
        )
    if kpi_id == 5:
        client_id = extra.get("client_id")
        if client_id is None:
            return (None, [])
        if not use_join:
            return (
                "SELECT id_produs, SUM(cantitate) AS total_bucati FROM Comenzi "
                "WHERE id_client = ? GROUP BY id_produs ORDER BY total_bucati DESC",
                [client_id],
            )
        return (
            "SELECT p.denumire AS produs, SUM(c.cantitate) AS total_bucati FROM Comenzi c "
            "JOIN Produse p ON c.id_produs = p.id_produs WHERE c.id_client = ? "
            "GROUP BY p.id_produs, p.denumire ORDER BY total_bucati DESC",
            [client_id],
        )
    if kpi_id == 6:
        if not use_join:
            return (
                "SELECT id_produs, COUNT(*) AS nr_comenzi FROM Comenzi "
                "GROUP BY id_produs ORDER BY nr_comenzi DESC",
                [],
            )
        return (
            "SELECT p.denumire AS produs, COUNT(*) AS nr_comenzi FROM Comenzi c "
            "JOIN Produse p ON c.id_produs = p.id_produs GROUP BY p.id_produs, p.denumire ORDER BY nr_comenzi DESC",
            [],
        )
    if kpi_id == 7:
        if not use_join:
            return (
                "SELECT id_furnizor, COUNT(*) AS nr_produse FROM Produse "
                "GROUP BY id_furnizor ORDER BY nr_produse DESC",
                [],
            )
        return (
            "SELECT f.nume AS furnizor, COUNT(*) AS nr_produse FROM Produse p "
            "JOIN Furnizori f ON p.id_furnizor = f.id_furnizor GROUP BY f.id_furnizor, f.nume ORDER BY nr_produse DESC",
            [],
        )
    if kpi_id == 8:
        if not use_join:
            return (
                "SELECT id_produs, COUNT(id_comanda) AS nr_comenzi FROM Comenzi "
                "GROUP BY id_produs ORDER BY nr_comenzi DESC",
                [],
            )
        return (
            "SELECT p.denumire AS produs, COUNT(c.id_comanda) AS nr_comenzi FROM Comenzi c "
            "JOIN Produse p ON c.id_produs = p.id_produs GROUP BY p.id_produs, p.denumire ORDER BY nr_comenzi DESC",
            [],
        )
    if kpi_id == 9:
        if not use_join:
            return (
                "SELECT id_produs, stoc, total_bucati FROM ("
                "SELECT p.id_produs, p.stoc, COALESCE(SUM(c.cantitate), 0) AS total_bucati "
                "FROM Produse p LEFT JOIN Comenzi c ON p.id_produs = c.id_produs "
                "GROUP BY p.id_produs, p.stoc) t WHERE stoc > 50 AND total_bucati < 5 ORDER BY stoc DESC",
                [],
            )
        return (
            "SELECT p.denumire AS produs, cat.denumire AS categorie, p.stoc, COALESCE(SUM(c.cantitate), 0) AS total_bucati "
            "FROM Produse p LEFT JOIN Comenzi c ON p.id_produs = c.id_produs "
            "LEFT JOIN Categorii cat ON p.id_categorie = cat.id_categorie "
            "GROUP BY p.id_produs, p.denumire, cat.denumire, p.stoc "
            "HAVING p.stoc > 50 AND COALESCE(SUM(c.cantitate), 0) < 5 ORDER BY p.stoc DESC",
            [],
        )
    if kpi_id == 10:
        if not use_join:
            return (
                "SELECT id_categorie, AVG(pret) AS pret_mediu FROM Produse "
                "GROUP BY id_categorie ORDER BY id_categorie",
                [],
            )
        return (
            "SELECT cat.denumire AS categorie, AVG(p.pret) AS pret_mediu FROM Produse p "
            "JOIN Categorii cat ON p.id_categorie = cat.id_categorie "
            "GROUP BY cat.id_categorie, cat.denumire ORDER BY pret_mediu DESC",
            [],
        )
    return (None, [])


def run_kpi_query(kpi_id: int, use_join: bool, conn: sqlite3.Connection, extra: dict | None = None) -> pd.DataFrame | None:
    """Execută SQL-ul KPI (folosind get_kpi_sql) și returnează DataFrame-ul."""
    sql, params = get_kpi_sql(kpi_id, use_join, extra)
    if sql is None:
        return None
    return pd.read_sql_query(sql, conn, params=params if params else None)


KPI_LIST = [
    {
        "id": 1,
        "name": "Produse cu stoc < 30",
        "objective": "Identificarea produselor cu stoc critic",
        "formula": "SELECT produse cu stoc < 30",
    },
    {
        "id": 2,
        "name": "Total vânzări pe categorie",
        "objective": "Creșterea vânzărilor pe categorie",
        "formula": "SUM(total) GROUP BY categorie",
    },
    {
        "id": 3,
        "name": "Produse cu vânzări reduse",
        "objective": "Identificarea produselor cu total vândut < 5 bucăți",
        "formula": "SUM(cantitate) GROUP BY produs",
    },
    {
        "id": 4,
        "name": "Total cheltuit per client",
        "objective": "Fidelizarea clienților",
        "formula": "SUM(total) GROUP BY client",
    },
    {
        "id": 5,
        "name": "Produse cumpărate de un client",
        "objective": "Identificarea produselor cumpărate de un anumit client",
        "formula": "JOIN Comenzi–Produse–Clienti + WHERE client",
    },
    {
        "id": 6,
        "name": "Nr. comenzi per produs",
        "objective": "Identificarea produselor populare",
        "formula": "COUNT(Comenzi) GROUP BY produs",
    },
    {
        "id": 7,
        "name": "Nr. produse per furnizor",
        "objective": "Evaluarea furnizorilor",
        "formula": "COUNT(Produse) GROUP BY furnizor",
    },
    {
        "id": 8,
        "name": "Număr comenzi per produs (JOIN)",
        "objective": "Determinarea popularității produselor",
        "formula": "JOIN Produse–Comenzi + COUNT(id_comanda)",
    },
    {
        "id": 9,
        "name": "Produse cu stoc mare și vânzări mici",
        "objective": "Produse cu stoc > 50 și vânzări mici",
        "formula": "JOIN Produse–Comenzi + HAVING stoc > 50 AND SUM(cantitate) < 5",
    },
    {
        "id": 10,
        "name": "Preț mediu pe categorie",
        "objective": "Analiza structurii prețurilor",
        "formula": "AVG(pret)",
    },
]


def page_kpi():
    """Pagina 4: KPI-uri, dropdown, formule SQL, charturi per KPI, timp salvat local, grafic timp mai jos."""
    st.header("📊 KPI magazin")

    if not os.path.isfile(DB_PATH):
        st.error(f"Nu am găsit fișierul bazei de date: `{DB_PATH}` (în același folder cu `main.py`).")
        return

    try:
        with sqlite3.connect(DB_PATH) as conn:
            labels = [f"{item['id']}. {item['name']}" for item in KPI_LIST]
            selected_label = st.selectbox("Alege un KPI", labels, key="kpi_dropdown")
            selected_id = int(selected_label.split(".")[0])
            kpi = next(item for item in KPI_LIST if item["id"] == selected_id)

            st.subheader(kpi["name"])
            st.markdown(f"**Obiectiv:** {kpi['objective']}")
            st.markdown(f"**Formula:** `{kpi['formula']}`")
            extra_display = {}
            
            extra_display = {}
            if kpi["id"] == 5:
                clients_df = pd.read_sql_query("SELECT id_client, nume FROM Clienti ORDER BY nume", conn)
                if not clients_df.empty:
                    extra_display["client_id"] = int(clients_df.iloc[0]["id_client"])
            
            st.markdown("**SQL pentru acest KPI:**")
            sql_simple, _ = get_kpi_sql(kpi["id"], False, extra_display)
            sql_join, _ = get_kpi_sql(kpi["id"], True, extra_display)
            if sql_simple is not None:
                with st.expander("Fără JOIN (query simplu)", expanded=True):
                    st.code(sql_simple, language="sql")
            if sql_join is not None:
                with st.expander("Cu JOIN", expanded=False):
                    st.code(sql_join, language="sql")
            if kpi["id"] == 5:
                st.caption("Pentru KPI 5, parametrul `?` din SQL este id_client (alege clientul mai jos).")
            
            query_type_label = st.radio(
                "Tip query",
                ["Fără JOIN (simplu)", "Cu JOIN"],
                horizontal=True,
                key=f"kpi_query_type_{kpi['id']}",
            )
            use_join = query_type_label == "Cu JOIN"
            extra_params: dict = {}
            if kpi["id"] == 5:
                if clients_df.empty:
                    st.warning("Nu există clienți în baza de date.")
                    return
                client_labels = [f"{row['id_client']} - {row['nume']}" for _, row in clients_df.iterrows()]
                selected_client = st.selectbox("Alege clientul", client_labels, key="kpi_client_selector")
                extra_params["client_id"] = int(selected_client.split(" - ")[0])

            run = st.button("Rulează query pentru acest KPI", key=f"run_kpi_{kpi['id']}")
            
            df_to_show = None
            duration_to_show: float | None = None

            if run:
                start = time.perf_counter()
                df_result = run_kpi_query(kpi["id"], use_join, conn, extra_params)
                duration_ms = (time.perf_counter() - start) * 1000
                st.session_state["kpi_last_result"] = {
                    "kpi_id": kpi["id"],
                    "use_join": use_join,
                    "df": df_result,
                    "duration_ms": duration_ms,
                }
                st.session_state["kpi_log"].append(
                    {
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "kpi_id": kpi["id"],
                        "kpi_name": kpi["name"],
                        "query_type": "JOIN" if use_join else "Simplu",
                        "duration_ms": duration_ms,
                    }
                )
                save_kpi_log(st.session_state["kpi_log"])
                df_to_show = df_result
                duration_to_show = duration_ms
            else:
                last = st.session_state.get("kpi_last_result")
                if last and last.get("kpi_id") == kpi["id"]:
                    df_to_show = last.get("df")
                    duration_to_show = last.get("duration_ms")
            
            if df_to_show is not None and duration_to_show is not None:
                st.markdown(f"**Timp execuție (ultimul run):** `{duration_to_show:.2f} ms`")

                if df_to_show is None or df_to_show.empty:
                    st.info("Query-ul nu a returnat date.")
                else:
                    render_table_with_border(df_to_show)
                    st.markdown("**Charturi rezultat KPI**")
                    kpi_chart_type = st.selectbox(
                        "Tip chart rezultat",
                        ["Bar", "Line", "Scatter"],
                        key=f"kpi_result_chart_type_{kpi['id']}",
                    )
                    
                    if kpi["id"] == 1 and "stoc" in df_to_show.columns:
                        label_col = "denumire"
                        if "produs" in df_to_show.columns:
                            label_col = "produs"
                        if label_col in df_to_show.columns:
                            chart_df = df_to_show.set_index(label_col)[["stoc"]]
                        else:
                            chart_df = df_to_show[["stoc"]]
                    else:
                        
                        chart_df = (
                            df_to_show.set_index(df_to_show.columns[0])
                            if len(df_to_show.columns) > 1
                            else df_to_show
                        )
                    if kpi_chart_type == "Bar":
                        st.bar_chart(chart_df, height=400)
                    elif kpi_chart_type == "Line":
                        st.line_chart(chart_df, height=400)
                    else:
                        st.scatter_chart(chart_df, height=400)

        
        st.markdown("---")
        st.subheader("Timp mediu de execuție query (ms)")
        if st.session_state.get("kpi_log"):
            log_df = pd.DataFrame(st.session_state["kpi_log"])
            agg = (
                log_df.groupby(["kpi_id", "kpi_name", "query_type"], as_index=False)["duration_ms"]
                .mean()
            )
            pivot = agg.pivot(index="kpi_name", columns="query_type", values="duration_ms")
            pivot = pivot.sort_index()

            timp_chart_type = st.selectbox(
                "Tip chart timp",
                ["Bar", "Line", "Scatter"],
                key="kpi_timp_chart_type",
            )
            if timp_chart_type == "Bar":
                st.bar_chart(pivot, height=450)
            elif timp_chart_type == "Line":
                st.line_chart(pivot, height=450)
            else:
                st.scatter_chart(pivot, height=450)

            st.caption(
                "Timpul este salvat local în `kpi_timings.json`. Compară timpul mediu pentru query simplu vs cu JOIN."
            )
        else:
            st.info("Rulează cel puțin un query KPI (butonul de mai sus) pentru a înregistra timpii și a afișa graficul.")
    except Exception as e:
        st.error(f"Eroare: {e}")


def main():
    init_session_state()
    render_sidebar()
    render_navbar()

    if st.session_state.current_page == "query":
        page_query()
    elif st.session_state.current_page == "schema":
        page_schema()
    elif st.session_state.current_page == "tables":
        page_tables()
    elif st.session_state.current_page == "kpi":
        page_kpi()


if __name__ == "__main__":
    main()
