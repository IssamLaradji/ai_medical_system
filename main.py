from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import datetime
import os
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Set
from agents import CancellationEmailAgent, EmailAgent


# Classes and functions from main.py
class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


@dataclass
class Patient:
    id: int
    name: str
    email: str
    phone: str
    address: str
    birthday: datetime.date
    preferred_clinicians: List[str] = None
    family_members: List[str] = None

    def __post_init__(self):
        if self.preferred_clinicians is None:
            self.preferred_clinicians = []
        if self.family_members is None:
            self.family_members = []


@dataclass
class Clinician:
    id: int
    name: str
    specialization: str
    available_hours: Dict[str, List[datetime.time]] = None

    def __post_init__(self):
        if self.available_hours is None:
            # Default availability (9 AM to 5 PM, Monday to Friday)
            self.available_hours = {
                "Monday": [datetime.time(9, 0), datetime.time(17, 0)],
                "Tuesday": [datetime.time(9, 0), datetime.time(17, 0)],
                "Wednesday": [datetime.time(9, 0), datetime.time(17, 0)],
                "Thursday": [datetime.time(9, 0), datetime.time(17, 0)],
                "Friday": [datetime.time(9, 0), datetime.time(17, 0)],
            }


@dataclass
class Appointment:
    id: int
    patient_id: int
    clinician_id: int
    date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
    status: str = "Scheduled"  # Scheduled, Completed, Cancelled, Rescheduled


@dataclass
class WaitlistEntry:
    patient_id: int
    requested_date: datetime.date
    priority: Priority
    preferred_clinician_ids: List[int] = None
    date_added: datetime.date = None

    def __post_init__(self):
        if self.preferred_clinician_ids is None:
            self.preferred_clinician_ids = []
        if self.date_added is None:
            self.date_added = datetime.date.today()


class AppointmentSystem:
    def __init__(self):
        self.patients: Dict[int, Patient] = {}
        self.clinicians: Dict[int, Clinician] = {}
        self.appointments: Dict[int, Appointment] = {}
        self.waitlist: List[WaitlistEntry] = []
        self.holidays: Set[datetime.date] = set()
        self.next_id = 1

    def add_patient(
        self,
        name,
        email,
        phone,
        address,
        birthday,
        preferred_clinicians=None,
        family_members=None,
    ) -> int:
        patient_id = self.next_id
        self.next_id += 1

        self.patients[patient_id] = Patient(
            id=patient_id,
            name=name,
            email=email,
            phone=phone,
            address=address,
            birthday=birthday,
            preferred_clinicians=preferred_clinicians or [],
            family_members=family_members or [],
        )
        return patient_id

    def add_clinician(self, name, specialization, available_hours=None) -> int:
        clinician_id = self.next_id
        self.next_id += 1

        self.clinicians[clinician_id] = Clinician(
            id=clinician_id,
            name=name,
            specialization=specialization,
            available_hours=available_hours,
        )
        return clinician_id

    def schedule_appointment(
        self, patient_id, clinician_id, date, start_time, end_time
    ) -> Optional[int]:
        # Check if date is a holiday
        if date in self.holidays:
            return None

        # Check if clinician exists
        if clinician_id not in self.clinicians:
            return None

        # Check if patient exists
        if patient_id not in self.patients:
            return None

        # Check clinician availability
        day_of_week = date.strftime("%A")
        clinician = self.clinicians[clinician_id]

        if day_of_week not in clinician.available_hours:
            return None

        avail_start, avail_end = clinician.available_hours[day_of_week]
        if start_time < avail_start or end_time > avail_end:
            return None

        # Check for conflicts with existing appointments
        for appt in self.appointments.values():
            if (
                appt.clinician_id == clinician_id
                and appt.date == date
                and appt.status != "Cancelled"
                and (
                    (start_time >= appt.start_time and start_time < appt.end_time)
                    or (end_time > appt.start_time and end_time <= appt.end_time)
                    or (start_time <= appt.start_time and end_time >= appt.end_time)
                )
            ):
                return None

        # Create the appointment
        appointment_id = self.next_id
        self.next_id += 1

        self.appointments[appointment_id] = Appointment(
            id=appointment_id,
            patient_id=patient_id,
            clinician_id=clinician_id,
            date=date,
            start_time=start_time,
            end_time=end_time,
        )

        # Send notification (simulated)
        self._send_appointment_confirmation(appointment_id)

        return appointment_id

    def cancel_appointment(self, appointment_id) -> bool:
        if appointment_id not in self.appointments:
            return False

        appointment = self.appointments[appointment_id]
        if appointment.status == "Cancelled":
            return False

        appointment.status = "Cancelled"

        # Send cancellation notification (simulated)
        self._send_cancellation_notification(appointment_id)

        # Try to fill the slot from waitlist
        self._fill_cancelled_slot(appointment)

        return True

    def add_to_waitlist(
        self, patient_id, requested_date, priority, preferred_clinician_ids=None
    ) -> bool:
        if patient_id not in self.patients:
            return False

        entry = WaitlistEntry(
            patient_id=patient_id,
            requested_date=requested_date,
            priority=priority,
            preferred_clinician_ids=preferred_clinician_ids or [],
        )

        self.waitlist.append(entry)

        # Sort waitlist by priority and then by date added
        self.waitlist.sort(key=lambda x: (-x.priority.value, x.date_added))

        return True

    def _fill_cancelled_slot(self, cancelled_appointment) -> Optional[int]:
        """Attempt to fill a cancelled slot with a patient from the waitlist."""
        date = cancelled_appointment.date
        clinician_id = cancelled_appointment.clinician_id
        start_time = cancelled_appointment.start_time
        end_time = cancelled_appointment.end_time

        # Find suitable patients from waitlist
        for i, entry in enumerate(self.waitlist):
            # Check if the patient wants this date or a clinician
            if entry.requested_date == date or (
                not entry.preferred_clinician_ids
                or clinician_id in entry.preferred_clinician_ids
            ):

                # Try to schedule
                new_appt_id = self.schedule_appointment(
                    entry.patient_id, clinician_id, date, start_time, end_time
                )

                if new_appt_id:
                    # Remove from waitlist
                    self.waitlist.pop(i)

                    # Send notification about the new appointment
                    self._send_waitlist_notification(new_appt_id)
                    return new_appt_id

        return None

    def _send_appointment_confirmation(self, appointment_id):
        """Simulate sending an appointment confirmation."""
        pass

    def _send_cancellation_notification(self, appointment_id):
        """Simulate sending a cancellation notification."""
        pass

    def _send_waitlist_notification(self, appointment_id):
        """Simulate sending a notification about an appointment from waitlist."""
        pass

    def get_clinician_schedule(self, clinician_id, date):
        """Get all appointments for a clinician on a specific date."""
        if clinician_id not in self.clinicians:
            return []

        schedule = []
        for appt in self.appointments.values():
            if (
                appt.clinician_id == clinician_id
                and appt.date == date
                and appt.status != "Cancelled"
            ):
                schedule.append(appt)

        # Sort by start time
        schedule.sort(key=lambda x: x.start_time)
        return schedule

    def get_patient_appointments(self, patient_id):
        """Get all appointments for a patient."""
        if patient_id not in self.patients:
            return []

        patient_appts = []
        for appt in self.appointments.values():
            if appt.patient_id == patient_id and appt.status != "Cancelled":
                patient_appts.append(appt)

        # Sort by date and start time
        patient_appts.sort(key=lambda x: (x.date, x.start_time))
        return patient_appts


# Flask app setup
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize the appointment system
system = AppointmentSystem()

# Sample emails for the inbox
sample_emails = [
    {
        "id": 1,
        "sender": "Jane Smith",
        "email": "jane.smith@example.com",
        "subject": "Appointment Rescheduling Request",
        "content": "Hello,\n\nI need to reschedule my appointment that's currently set for Friday, May 12th at 2:30 PM with Dr. Williams. I have an unexpected work conflict that came up. Do you have any availability next week, preferably in the afternoon?\n\nI apologize for any inconvenience this may cause.\n\nThank you,\nJane Smith\n(555) 987-6543",
        "date": datetime.datetime.now() - datetime.timedelta(days=1, hours=3),
        "read": False,
    },
    {
        "id": 2,
        "sender": "John Doe",
        "email": "john.doe@example.com",
        "subject": "Medical Records Request",
        "content": "Good morning,\n\nI have an appointment with Dr. Sarah Johnson, a cardiologist at Memorial Hospital, on June 3rd. She has requested my complete medical history and recent lab results.\n\nCould you please prepare these records and send them to me as soon as possible? I can pick them up in person if needed, or you can send them securely to my patient portal.\n\nMy date of birth is 04/15/1978 for verification purposes.\n\nThanks,\nJohn Doe\n(555) 123-4567",
        "date": datetime.datetime.now() - datetime.timedelta(hours=5),
        "read": False,
    },
    {
        "id": 3,
        "sender": "Michael Johnson",
        "email": "michael.johnson@example.com",
        "subject": "Insurance Coverage Question",
        "content": "To whom it may concern,\n\nI recently changed my insurance provider from BlueCross to ABC Health Insurance and wanted to confirm that you accept this new insurance before my upcoming appointment next month.\n\nMy new policy information is:\n- Provider: ABC Health Insurance\n- Policy Number: ABC-12345678\n- Group Number: G-987654\n- Effective Date: May 1, 2023\n\nPlease let me know if you need any additional information or if I need to update anything in your system before my visit.\n\nBest regards,\nMichael Johnson\n(555) 789-0123",
        "date": datetime.datetime.now() - datetime.timedelta(hours=2),
        "read": False,
    },
]


# Add some sample data
def initialize_sample_data():
    # Add clinicians
    dr_smith = system.add_clinician("Dr. Smith", "General Practitioner")
    dr_jones = system.add_clinician("Dr. Jones", "Pediatrician")
    dr_wilson = system.add_clinician(
        "Dr. Wilson",
        "Dermatologist",
        {
            "Monday": [datetime.time(10, 0), datetime.time(18, 0)],
            "Wednesday": [datetime.time(10, 0), datetime.time(18, 0)],
            "Friday": [datetime.time(10, 0), datetime.time(18, 0)],
        },
    )

    # Add patients
    john = system.add_patient(
        "John Doe",
        "john@example.com",
        "555-1234",
        "123 Main St",
        datetime.date(1980, 5, 15),
        preferred_clinicians=["Dr. Smith"],
    )

    jane = system.add_patient(
        "Jane Smith",
        "jane@example.com",
        "555-5678",
        "456 Oak Ave",
        datetime.date(1992, 8, 22),
        preferred_clinicians=["Dr. Wilson"],
        family_members=["Michael Smith", "Emma Smith"],
    )

    # Add some holidays
    system.holidays.add(datetime.date(2023, 12, 25))  # Christmas
    system.holidays.add(datetime.date(2024, 1, 1))  # New Year's Day

    # Schedule a few appointments
    next_monday = datetime.date.today() + datetime.timedelta(
        days=(7 - datetime.date.today().weekday())
    )

    system.schedule_appointment(
        john, dr_smith, next_monday, datetime.time(9, 0), datetime.time(9, 30)
    )

    system.schedule_appointment(
        jane, dr_wilson, next_monday, datetime.time(10, 0), datetime.time(10, 30)
    )


initialize_sample_data()


@app.route("/")
def index():
    return render_template(
        "index.html",
        patients=system.patients,
        clinicians=system.clinicians,
        appointments=system.appointments,
        waitlist=system.waitlist,
        emails=sample_emails,
    )


@app.route("/patients")
def patients():
    return render_template("patients.html", patients=system.patients)


@app.route("/add_patient", methods=["POST"])
def add_patient():
    try:
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        address = request.form["address"]
        birthday = datetime.datetime.strptime(
            request.form["birthday"], "%Y-%m-%d"
        ).date()

        preferred_clinicians = (
            request.form.get("preferred_clinicians", "").split(",")
            if request.form.get("preferred_clinicians")
            else []
        )
        family_members = (
            request.form.get("family_members", "").split(",")
            if request.form.get("family_members")
            else []
        )

        patient_id = system.add_patient(
            name,
            email,
            phone,
            address,
            birthday,
            preferred_clinicians=preferred_clinicians,
            family_members=family_members,
        )

        flash(f"Patient {name} added successfully!", "success")
    except Exception as e:
        flash(f"Error adding patient: {str(e)}", "danger")

    return redirect(url_for("index"))


@app.route("/clinicians")
def clinicians():
    return render_template("clinicians.html", clinicians=system.clinicians)


@app.route("/add_clinician", methods=["POST"])
def add_clinician():
    try:
        name = request.form["name"]
        specialization = request.form["specialization"]

        # For simplicity, we're using default hours
        clinician_id = system.add_clinician(name, specialization)

        flash(f"Clinician {name} added successfully!", "success")
    except Exception as e:
        flash(f"Error adding clinician: {str(e)}", "danger")

    return redirect(url_for("index"))


@app.route("/schedule_appointment", methods=["POST"])
def schedule_appointment():
    try:
        patient_id = int(request.form["patient_id"])
        clinician_id = int(request.form["clinician_id"])
        date_str = request.form["date"]
        start_time_str = request.form["start_time"]
        end_time_str = request.form["end_time"]

        date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        start_time = datetime.datetime.strptime(start_time_str, "%H:%M").time()
        end_time = datetime.datetime.strptime(end_time_str, "%H:%M").time()

        appointment_id = system.schedule_appointment(
            patient_id, clinician_id, date, start_time, end_time
        )

        if appointment_id:
            flash("Appointment scheduled successfully!", "success")
        else:
            flash("Failed to schedule appointment.", "danger")
    except Exception as e:
        flash(f"Error scheduling appointment: {str(e)}", "danger")

    return redirect(url_for("index"))


@app.route("/cancel_appointment/<int:appointment_id>", methods=["POST"])
def cancel_appointment(appointment_id):
    try:
        # Get appointment details before cancellation
        if appointment_id in system.appointments:
            appointment = system.appointments[appointment_id]
            patient = system.patients[appointment.patient_id]
            clinician = system.clinicians[appointment.clinician_id]

            # Generate cancellation email
            email_agent = CancellationEmailAgent()
            cancellation_email = email_agent.generate_email(
                patient_name=patient.name,
                appointment_date=appointment.date.strftime("%Y-%m-%d"),
                appointment_time=f"{appointment.start_time.strftime('%H:%M')} - {appointment.end_time.strftime('%H:%M')}",
                clinician_name=clinician.name,
            )

            # Store email and appointment details in session for the modal
            appointment_details = {
                "id": appointment_id,
                "patient_name": patient.name,
                "patient_id": patient.id,
                "email": patient.email,
                "cancellation_email": cancellation_email,
            }

            # Return JSON response with email content and details
            return jsonify(appointment_details)
        else:
            flash("Appointment not found.", "danger")
            return jsonify({"error": "Appointment not found"}), 404
    except Exception as e:
        flash(f"Error processing cancellation: {str(e)}", "danger")
        return jsonify({"error": str(e)}), 500


@app.route("/confirm_cancellation", methods=["POST"])
def confirm_cancellation():
    try:
        appointment_id = int(request.form.get("appointment_id"))
        email_approved = request.form.get("email_approved") == "true"

        if email_approved:
            # In a real application, you would send the email here
            # For now, we'll just cancel the appointment
            if system.cancel_appointment(appointment_id):
                flash("Appointment cancelled and email sent successfully!", "success")
            else:
                flash("Failed to cancel appointment.", "danger")
        else:
            flash("Cancellation rejected. Appointment remains scheduled.", "warning")

        return redirect(url_for("index"))
    except Exception as e:
        flash(f"Error confirming cancellation: {str(e)}", "danger")
        return redirect(url_for("index"))


@app.route("/send_cancellation_email", methods=["POST"])
def send_cancellation_email():
    email_content = request.form.get("email_content")
    patient_name = request.form.get("patient_name")
    appointment_id = request.form.get("appointment_id")

    # In a real application, you would send the email here
    # For now, we'll just simulate it with a flash message

    flash(f"Cancellation email sent to {patient_name}!", "success")
    return redirect(url_for("index"))


@app.route("/reject_cancellation_email", methods=["POST"])
def reject_cancellation_email():
    appointment_id = request.form.get("appointment_id")

    # If the email is rejected, we need to restore the appointment
    # In a real application, you might want to handle this differently
    flash(
        "Email rejected. Please cancel the appointment again or handle manually.",
        "warning",
    )
    return redirect(url_for("index"))


@app.route("/add_to_waitlist", methods=["POST"])
def add_to_waitlist():
    try:
        patient_id = int(request.form["patient_id"])
        date_str = request.form["requested_date"]
        priority_value = int(request.form["priority"])

        requested_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        priority = Priority(priority_value)

        preferred_clinician_ids = []
        if request.form.get("preferred_clinician_ids"):
            preferred_clinician_ids = [
                int(id) for id in request.form.get("preferred_clinician_ids").split(",")
            ]

        if system.add_to_waitlist(
            patient_id, requested_date, priority, preferred_clinician_ids
        ):
            flash("Patient added to waitlist successfully!", "success")
        else:
            flash("Failed to add patient to waitlist.", "danger")
    except Exception as e:
        flash(f"Error adding to waitlist: {str(e)}", "danger")

    return redirect(url_for("index"))


@app.route("/get_clinician_schedule", methods=["GET"])
def get_clinician_schedule():
    clinician_id = int(request.args.get("clinician_id"))
    date_str = request.args.get("date")
    date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()

    schedule = system.get_clinician_schedule(clinician_id, date)

    # Convert to a format suitable for JSON
    schedule_data = []
    for appt in schedule:
        patient = system.patients[appt.patient_id]
        schedule_data.append(
            {
                "id": appt.id,
                "patient_name": patient.name,
                "start_time": appt.start_time.strftime("%H:%M"),
                "end_time": appt.end_time.strftime("%H:%M"),
                "status": appt.status,
            }
        )

    return jsonify(schedule_data)


@app.route("/get_patient_appointments", methods=["GET"])
def get_patient_appointments():
    patient_id = int(request.args.get("patient_id"))

    appointments = system.get_patient_appointments(patient_id)

    # Convert to a format suitable for JSON
    appointment_data = []
    for appt in appointments:
        clinician = system.clinicians[appt.clinician_id]
        appointment_data.append(
            {
                "id": appt.id,
                "clinician_name": clinician.name,
                "date": appt.date.strftime("%Y-%m-%d"),
                "start_time": appt.start_time.strftime("%H:%M"),
                "end_time": appt.end_time.strftime("%H:%M"),
                "status": appt.status,
            }
        )

    return jsonify(appointment_data)


@app.route("/get_email_response/<int:email_id>", methods=["GET"])
def get_email_response(email_id):
    try:
        # Find the email by ID
        email = next((e for e in sample_emails if e["id"] == email_id), None)

        if not email:
            return jsonify({"error": "Email not found"}), 404

        # Mark email as read
        email["read"] = True

        # Generate response using EmailAgent
        email_agent = EmailAgent()
        response = email_agent.generate_response(
            sender_name=email["sender"],
            email_subject=email["subject"],
            email_content=email["content"],
        )

        return jsonify(
            {
                "id": email["id"],
                "sender": email["sender"],
                "email": email["email"],
                "subject": email["subject"],
                "content": email["content"],
                "response": response,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/send_email_response", methods=["POST"])
def send_email_response():
    try:
        email_id = int(request.form.get("email_id"))
        response_content = request.form.get("response_content")

        # Find the email by ID
        email = next((e for e in sample_emails if e["id"] == email_id), None)

        if not email:
            flash("Email not found.", "danger")
            return redirect(url_for("index"))

        # In a real application, you would send the email here
        # For now, we'll just simulate it with a flash message
        flash(f"Response sent to {email['sender']} ({email['email']})!", "success")

        # Remove the email from the inbox
        sample_emails.remove(email)

        return redirect(url_for("index"))

    except Exception as e:
        flash(f"Error sending response: {str(e)}", "danger")
        return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=7776)
