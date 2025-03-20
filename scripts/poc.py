import datetime
import random
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Set


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
        # Method body kept empty after removing print statements
        pass

    def _send_cancellation_notification(self, appointment_id):
        """Simulate sending a cancellation notification."""
        # Method body kept empty after removing print statements
        pass

    def _send_waitlist_notification(self, appointment_id):
        """Simulate sending a notification about an appointment from waitlist."""
        # Method body kept empty after removing print statements
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


# Demo function to showcase the system
def run_demo():
    system = AppointmentSystem()

    # Add some holidays
    system.holidays.add(datetime.date(2023, 12, 25))  # Christmas
    system.holidays.add(datetime.date(2023, 1, 1))  # New Year's Day

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

    bob = system.add_patient(
        "Bob Johnson",
        "bob@example.com",
        "555-9012",
        "789 Pine Rd",
        datetime.date(1975, 3, 10),
    )

    # Schedule appointments
    next_monday = datetime.date.today() + datetime.timedelta(
        days=(7 - datetime.date.today().weekday())
    )

    # John's appointment with Dr. Smith
    appt1 = system.schedule_appointment(
        john, dr_smith, next_monday, datetime.time(9, 0), datetime.time(9, 30)
    )

    # Jane's appointment with Dr. Wilson
    appt2 = system.schedule_appointment(
        jane, dr_wilson, next_monday, datetime.time(10, 0), datetime.time(10, 30)
    )

    # Try to schedule an appointment on a holiday (should fail)
    system.schedule_appointment(
        bob,
        dr_smith,
        datetime.date(2023, 12, 25),
        datetime.time(9, 0),
        datetime.time(9, 30),
    )

    # Add Bob to the waitlist
    system.add_to_waitlist(bob, next_monday, Priority.HIGH, [dr_smith, dr_jones])

    # Cancel Jane's appointment (should trigger waitlist processing)
    if appt2:
        system.cancel_appointment(appt2)

    # Get Dr. Smith's schedule for next Monday
    schedule = system.get_clinician_schedule(dr_smith, next_monday)

    # Get John's appointments
    john_appts = system.get_patient_appointments(john)


if __name__ == "__main__":
    run_demo()
