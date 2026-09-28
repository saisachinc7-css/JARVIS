import pywhatkit as kit
from datetime import datetime
import time
from os import getcwd

# Import speak function (assuming it's from your text_to_speech module)
# from text_to_speech.FastDTTS import speak

def clear_file():
    """Clear the file - implementation depends on your automation setup"""
    import_path = getcwd()
    # Add your file clearing logic here
    pass

def send_msg_on_WA(number, text):
    """
    Send WhatsApp message with time delay
    Args:
        number: Phone number to send message to (without +)
        text: Message text to send
    """
    # Get current time
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    
    # Send message at current hour and minute + 1
    kit.sendwhatmsg(number, text, hour, minute + 1)
    
def send_image_on_WA(number, image_path):
    """
    Send image on WhatsApp
    Args:
        number: Phone number to send to
        image_path: Relative path to image file
    """
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    
    kit.sendwhats_image(number, image_path, hour, minute + 1)

# Main automation logic for Jarvis integration
def whatsapp_automation(output_text):
    """
    Process voice commands for WhatsApp automation
    Args:
        output_text: The text command from voice recognition
    """
    
    # Check if command starts with "send to"
    if output_text.startswith("send to"):
        # Remove "send to" from the text
        output_text = output_text.replace("send to", "")
        
        # Check recipient name
        if "CONTACT_NAME_FOUR" in output_text:
            # Replace with your own number (without country code prefix)
            number = "1234567890"  # Replace with actual number
            
            # Speak confirmation
            # speak("By the way, what is the message sir?")
            
            # Clear file (if needed for your setup)
            clear_file()
            
            # Wait for 1 second
            time.sleep(1)
            
            # Get message from check function
            # Note: You need to implement your check() function
            # that listens for the message text
            # message = check()
            
            # For demo, using a placeholder
            message = "Hello, I am doing great"
            
            # Speak the message being sent
            # speak(f"Message is {message}")
            
            # Send the message
            send_msg_on_WA(number, message)
            
            # Confirm message sent
            # speak("Message send successfully")
            
    # Check if command starts with "send message on whatsapp"
    elif output_text.startswith("send message on"):
        output_text = output_text.replace("send message on", "")
        
        if "whatsapp" in output_text:
            # speak("To whom do you want to send sir?")
            clear_file()
            time.sleep(1)
            
            # Get recipient name
            # recipient = check()
            recipient = "CONTACT_NAME_FOUR"
            
            if "CONTACT_NAME_FOUR" in recipient:
                number = "1234567890"  # Replace with actual number
                
                # speak("By the way, what is the message sir?")
                clear_file()
                time.sleep(1)
                
                # Get message
                # message = check()
                message = "Hello, how can I assist you?"
                
                # Send message
                send_msg_on_WA(number, message)
                
                # Confirm
                # speak("Message send successfully")


# Database example - you can expand this
contacts_db = {
    "CONTACT_NAME_FOUR": "1234567890",
    # Add more contacts here
    # "john": "9876543210",
    # "jane": "5555555555"
}

# Example usage
if __name__ == "__main__":
    # Example 1: Direct message send
    # send_msg_on_WA("1234567890", "Hey this is demo")
    
    # Example 2: Using automation function
    # whatsapp_automation("send to CONTACT_NAME_FOUR")
    
    pass
