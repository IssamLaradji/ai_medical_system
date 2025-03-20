# suppress warnings
import warnings
import os
import json

warnings.filterwarnings("ignore")
from together import Together

# Get Client
with open("api_keys.json", "r") as f:
    api_keys = json.load(f)

your_api_key = api_keys["together"]
client = Together(api_key=your_api_key)


def prompt_llm(prompt, show_cost=False):
    # This function allows us to prompt an LLM via the Together API

    # model
    model = "meta-llama/Meta-Llama-3-8B-Instruct-Lite"

    # Calculate the number of tokens
    tokens = len(prompt.split())

    # Calculate and print estimated cost for each model
    if show_cost:
        print(f"\nNumber of tokens: {tokens}")
        cost = (0.1 / 1_000_000) * tokens
        print(f"Estimated cost for {model}: ${cost:.10f}\n")

    # Make the API call
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


# Add CancellationEmailAgent class
class CancellationEmailAgent:
    def generate_email(
        self, patient_name, appointment_date, appointment_time, clinician_name
    ):
        prompt = f"""
        Generate an empathetic email to a patient whose medical appointment has been canceled.
        
        Use this as an example of how to write an email to a patient whose appointment has been canceled:
        Example 1:
        Subject: Appointment Rescheduled
        Dear [Patient Name],
        I hope this message finds you well. I wanted to inform you that your upcoming appointment with Dr. [Clinician Name] has been rescheduled.
        The new date and time for your appointment are [New Date and Time].
        Please note that this change is due to unforeseen circumstances, and we apologize for any inconvenience this may cause.
        If you have any questions or need further assistance, please do not hesitate to contact us at [Office Phone Number].
        Thank you for your understanding and cooperation.
        Best regards,
        [Your Name]
        [Your Position]
        [Your Contact Information]
        
        
        - Patient Name: {patient_name}
        - Original Appointment Date: {appointment_date}
        - Original Appointment Time: {appointment_time}
        - Clinician: {clinician_name}
        
        INSTRUCTIONS:
        - Start with a respectful greeting
        - Express sincere apology for the cancellation
        - Briefly explain that unforeseen circumstances required rescheduling (without specifics)
        - Invite them to call the office to reschedule at their convenience
        - Provide the office phone number as (555) 123-4567
        - End with a professional and caring closing
        - Keep the tone empathetic, professional, and concise
        - The email should be 4-6 sentences total
        
        Write only the email content, with no additional commentary.
        """

        return prompt_llm(prompt)


# Add EmailAgent class
class EmailAgent:
    def generate_response(self, sender_name, email_subject, email_content):
        prompt = f"""
        Generate a professional and helpful response to the following email from a patient:
        
        From: {sender_name}
        Subject: {email_subject}
        Message: {email_content}
        
        INSTRUCTIONS:
        - Start with a polite greeting addressing the patient by name
        - Directly address their specific question or concern
        - Provide clear and helpful information
        - If appropriate, offer next steps or ask for additional information
        - End with a professional closing
        - Keep the tone warm, professional, and concise
        - The response should be 4-7 sentences total
        - Sign the email as "Medical Office Staff"
        
        Write only the email response content, with no additional commentary.
        """

        return prompt_llm(prompt)
