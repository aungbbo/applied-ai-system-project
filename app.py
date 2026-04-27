import streamlit as st

import rag_engine
from pawpal_system import Owner, Pet, Task, Scheduler

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

# ---------------------------------------------------------------------------
# Session state — the "vault" that survives reruns
# ---------------------------------------------------------------------------

if "owner" not in st.session_state:
    st.session_state.owner = None
if "scheduler" not in st.session_state:
    st.session_state.scheduler = None
if "last_schedule" not in st.session_state:
    st.session_state.last_schedule = None

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("🐾 PawPal+")
st.caption("A pet care planning assistant that builds your daily schedule.")

# ---------------------------------------------------------------------------
# 1. Owner setup
# ---------------------------------------------------------------------------

st.subheader("1 · Owner Setup")

with st.form("owner_form"):
    owner_name = st.text_input("Owner name", value="Jordan")
    available_minutes = st.number_input(
        "Available minutes today", min_value=1, max_value=480, value=90
    )
    save_owner = st.form_submit_button("Save owner")

if save_owner:
    if st.session_state.owner is None:
        st.session_state.owner = Owner(
            name=owner_name, available_minutes=available_minutes
        )
    else:
        st.session_state.owner.name = owner_name
        st.session_state.owner.available_minutes = available_minutes
    st.session_state.scheduler = Scheduler(st.session_state.owner)

if st.session_state.owner:
    st.success(f"Owner: **{st.session_state.owner}**")

st.divider()

# ---------------------------------------------------------------------------
# 2. Add pets
# ---------------------------------------------------------------------------

st.subheader("2 · Pets")

if st.session_state.owner is None:
    st.info("Save an owner first.")
else:
    owner: Owner = st.session_state.owner

    with st.form("pet_form"):
        col_pname, col_species = st.columns(2)
        with col_pname:
            pet_name = st.text_input("Pet name", value="Mochi")
        with col_species:
            species = st.selectbox("Species", ["dog", "cat", "other"])
        special_needs = st.text_input("Special needs (optional)", value="")
        add_pet = st.form_submit_button("Add pet")

    if add_pet:
        try:
            owner.add_pet(
                Pet(name=pet_name, species=species, special_needs=special_needs)
            )
            st.session_state.scheduler = Scheduler(owner)
        except ValueError as e:
            st.error(str(e))

    if owner.pets:
        for pet in owner.pets:
            col_info, col_btn = st.columns([4, 1])
            with col_info:
                needs = f" — {pet.special_needs}" if pet.special_needs else ""
                st.write(f"**{pet.name}** ({pet.species}){needs}")
            with col_btn:
                if st.button("Remove", key=f"rm_pet_{pet.name}"):
                    owner.remove_pet(pet.name)
                    st.session_state.scheduler = Scheduler(owner)
                    st.session_state.last_schedule = None
                    st.rerun()
    else:
        st.info("No pets yet.")

st.divider()

# ---------------------------------------------------------------------------
# 3. Add tasks
# ---------------------------------------------------------------------------

st.subheader("3 · Tasks")

if st.session_state.owner and st.session_state.owner.pets:
    pet_names = [p.name for p in st.session_state.owner.pets]

    with st.form("task_form"):
        selected_pet = st.selectbox("Add task to pet", pet_names)
        col1, col2, col3 = st.columns(3)
        with col1:
            task_title = st.text_input("Task title", value="Morning walk")
        with col2:
            duration = st.number_input(
                "Duration (min)", min_value=1, max_value=240, value=20
            )
        with col3:
            priority = st.selectbox("Priority", ["high", "medium", "low"])
        task_desc = st.text_input("Description (optional)", value="")
        col_cat, col_freq, col_time = st.columns(3)
        with col_cat:
            category = st.selectbox(
                "Category",
                ["exercise", "feeding", "medical", "grooming", "enrichment", "other"],
            )
        with col_freq:
            frequency = st.selectbox("Frequency", ["daily", "weekly", "as_needed"])
        with col_time:
            preferred_time = st.text_input("Preferred time (HH:MM)", value="")
        add_task = st.form_submit_button("Add task")

    if add_task:
        try:
            st.session_state.scheduler.add_task(
                selected_pet,
                Task(
                    title=task_title,
                    description=task_desc,
                    duration_minutes=int(duration),
                    priority=priority,
                    category=category,
                    frequency=frequency,
                    preferred_time=preferred_time,
                ),
            )
            st.success(f"Added **{task_title}** to {selected_pet}")
        except ValueError as e:
            st.error(str(e))

    # --- Task table per pet with inline actions ---
    for pet in st.session_state.owner.pets:
        if pet.tasks:
            st.markdown(f"**{pet.name}** — {pet.completion_summary()}")
            st.table([
                {
                    "Status": "✅" if t.completed else "⬜",
                    "Task": t.title,
                    "Time": t.preferred_time or "—",
                    "Duration": f"{t.duration_minutes} min",
                    "Priority": t.priority.capitalize(),
                    "Category": t.category.capitalize(),
                    "Frequency": t.frequency.replace("_", " ").capitalize(),
                }
                for t in pet.tasks
            ])
            col_actions = st.columns(len(pet.tasks))
            for idx, task in enumerate(pet.tasks):
                with col_actions[idx]:
                    if not task.completed:
                        if st.button("Done", key=f"done_{pet.name}_{task.title}"):
                            pet.complete_task(task.title)
                            st.rerun()
                    if st.button("Remove", key=f"rm_{pet.name}_{task.title}"):
                        pet.remove_task(task.title)
                        st.rerun()
else:
    st.info("Add an owner and pet above first.")

st.divider()

# ---------------------------------------------------------------------------
# 4. Sorted task overview (sort_by_time)
# ---------------------------------------------------------------------------

st.subheader("4 · Tasks by Preferred Time")

scheduler: Scheduler | None = st.session_state.scheduler
if scheduler and scheduler.get_all_pending():
    sorted_tasks = scheduler.sort_by_time()
    st.table([
        {
            "Pet": pet.name,
            "Task": task.title,
            "Preferred Time": task.preferred_time or "— (no time set)",
            "Priority": task.priority.capitalize(),
            "Duration": f"{task.duration_minutes} min",
        }
        for pet, task in sorted_tasks
    ])

    # --- Conflict warnings shown inline right after the sorted view ---
    conflicts = scheduler.detect_conflicts()
    if conflicts:
        st.warning(
            f"**{len(conflicts)} scheduling conflict{'s' if len(conflicts) > 1 else ''} detected**\n\n"
            "The following tasks have overlapping preferred times. "
            "The scheduler will still build a valid sequential plan, but you may "
            "want to adjust the times so the plan matches your real-life routine."
        )
        for w in conflicts:
            st.error(w)
    else:
        st.success("No scheduling conflicts — all preferred times are clear.")
else:
    st.info("Add tasks above to see them sorted by preferred time.")

st.divider()

# ---------------------------------------------------------------------------
# 5. Generate schedule
# ---------------------------------------------------------------------------

st.subheader("5 · Build Schedule")

if st.button("Generate schedule"):
    if scheduler is None:
        st.warning("Set up an owner and pets first.")
    elif not scheduler.get_all_pending():
        st.warning("Add at least one pending task before generating a schedule.")
    else:
        st.session_state.last_schedule = scheduler.generate_schedule()

if st.session_state.last_schedule:
    schedule = st.session_state.last_schedule
    total_min = sum(e.task.duration_minutes for e in schedule)
    budget = st.session_state.owner.available_minutes

    st.markdown("### 📋 Today's Schedule")
    st.progress(
        min(total_min / budget, 1.0),
        text=f"{total_min} / {budget} min used",
    )

    st.table([
        {
            "Time": f"{e.start_minute}–{e.end_minute()} min",
            "Pet": e.pet_name,
            "Task": e.task.title,
            "Duration": f"{e.task.duration_minutes} min",
            "Reason": e.reason,
        }
        for e in schedule
    ])

    # --- Conflict warnings inside the schedule view ---
    if scheduler and scheduler._last_warnings:
        with st.expander("⚠️ Preferred-time conflicts", expanded=True):
            st.caption(
                "These tasks have overlapping preferred times. The schedule "
                "above sequences them back-to-back, but in real life you "
                "can't do both at once. Consider adjusting the times."
            )
            for w in scheduler._last_warnings:
                st.warning(w)

    # --- Skipped tasks ---
    if scheduler:
        skipped = scheduler._skipped_tasks(schedule)
        if skipped:
            with st.expander("Tasks that didn't fit"):
                for pet, task in skipped:
                    st.info(
                        f"**[{pet.name}] {task.title}** — "
                        f"{task.duration_minutes} min, {task.priority} priority"
                    )

    st.divider()

    # --- Explanation ---
    with st.expander("Full explanation"):
        st.text(scheduler.explain_schedule(schedule))

    # --- Mark complete ---
    if st.button("Mark all scheduled tasks complete"):
        scheduler.mark_scheduled_complete()
        st.session_state.last_schedule = None
        st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# 6. Ask PawPal — RAG-powered pet care Q&A
# ---------------------------------------------------------------------------

st.subheader("6 · Ask PawPal 🐾")
st.caption("Ask a dog care question and get an answer grounded in our pet care knowledge base.")

if "rag_answer" not in st.session_state:
    st.session_state.rag_answer = None
if "rag_sources" not in st.session_state:
    st.session_state.rag_sources = []
if "rag_scores" not in st.session_state:
    st.session_state.rag_scores = []

with st.form("rag_form"):
    user_question = st.text_input(
        "Your question",
        placeholder="e.g. How often should I feed my large dog?",
    )
    ask_btn = st.form_submit_button("Ask PawPal")

if ask_btn:
    if not user_question.strip():
        st.warning("Please enter a question first.")
    else:
        with st.spinner("PawPal is thinking…"):
            try:
                answer, sources, scores = rag_engine.query(user_question.strip())
                st.session_state.rag_answer = answer
                st.session_state.rag_sources = sources
                st.session_state.rag_scores = scores
            except EnvironmentError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Something went wrong: {e}")

if st.session_state.rag_answer:
    st.markdown("### 💬 PawPal says")
    st.success(st.session_state.rag_answer)

    scores = st.session_state.rag_scores
    if scores:
        avg_score = sum(scores) / len(scores)
        top_score = max(scores)
        st.caption(
            f"Retrieval confidence — best match: **{top_score:.0%}** | "
            f"average: **{avg_score:.0%}** "
            f"({'🟢 High' if top_score >= 0.7 else '🟡 Medium' if top_score >= 0.4 else '🔴 Low'})"
        )

    if st.session_state.rag_sources:
        with st.expander("📄 Sources used"):
            for src, score in zip(st.session_state.rag_sources, st.session_state.rag_scores):
                st.markdown(f"- `{src}` — confidence: **{score:.0%}**")
