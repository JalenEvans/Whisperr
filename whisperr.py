import typer
import wave
import os
import struct
import base64
import time
from rich.progress import track
from rich.console import Console
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from pathlib import Path

app = typer.Typer(help="Convert text to audio and back.")

# Protocol Markers
DIR_START = b'\xff'
FILE_START = b'\xfe'
PROTECTED = b'\xfd'

def get_fernet(password: str, salt: bytes) -> Fernet:
    """
    Derives a fernet key from a password and salt
    
    :param password: Description
    :type password: str
    :param salt: Description
    :type salt: bytes
    :return: Description
    :rtype: Fernet
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))
    return Fernet(key)

@app.command()
def encode(
    src: Path = typer.Argument(..., help="The text file to convert."),
    output_file: Path = typer.Option("output.wav", "--output", "-o", help="The destination filepath for the audio file."),
    rate: int = typer.Option(44100, "--rate", "-r", help="Sample rate (lower = longer audio)"),
    protect: bool = typer.Option(False, "--protect", "-p", help="Encrypt your files before encoding and protect it with a password.")
):
    """
    Transform a file or directory into a playable .wav bitstream

    :param input_file: Description
    :type input_file: Path
    :param output_file: Description
    :type output_file: Path
    :param rate: Description
    :type rate: int
    """

    all_bytes = bytearray()

    if protect:
        entered_pass = typer.prompt("Password", hide_input=True, confirmation_prompt=True)
        salt = os.urandom(16)
        all_bytes.extend(PROTECTED + salt)

        fernet = get_fernet(entered_pass, salt)

    if src.is_dir():
        files_to_encode = []
        for root, dirs, files in os.walk(src):
            for name in dirs + files:
                files_to_encode.append(Path(root) / name)
                
        for file_path in track(files_to_encode, description="[cyan]Encoding text to audio..."):
            rel_path = file_path.relative_to(src)
            is_dir = file_path.is_dir()

            # Write Marker
            all_bytes.extend(DIR_START if is_dir else FILE_START)

            # Write Name Length + Name
            name_bytes = str(rel_path).encode('utf-8')
            all_bytes.extend(struct.pack(">I", len(name_bytes)))
            all_bytes.extend(name_bytes)

            if not is_dir:
                content_bytes = file_path.read_bytes()

                if protect:
                    # Encrypt files
                    encrypted_content = fernet.encrypt(content_bytes)
                    all_bytes.extend(struct.pack(">I", len(encrypted_content)))
                    all_bytes.extend(encrypted_content)
                else:
                    # Write the Content Length + Content
                    all_bytes.extend(struct.pack(">I", len(content_bytes)))
                    all_bytes.extend(content_bytes)
            time.sleep(0.01)
    else:
        if not src.exists():
            typer.secho(f"Input file {src} not found.", fg=typer.colors.RED)
            raise typer.Exit()
        
        if protect:
            all_bytes.extend(fernet.encrypt(src.read_bytes()))
        
        else:
            all_bytes.extend(src.read_bytes())

    with wave.open(str(output_file), "wb") as audio:
        audio.setnchannels(1) # Mono
        audio.setsampwidth(1) # 8-bit
        audio.setframerate(rate)
        audio.writeframes(all_bytes)

    typer.secho(f"Successfully encoded {src} into {output_file}", fg=typer.colors.GREEN)

console = Console()

@app.command()
def decode(
    input_file: Path = typer.Argument(..., help="The .wav file to decode."),
    output: Path = typer.Option("recovered", "--output", "-o", help="The destination filepath for the text file."),
):
    """
    Transform a .wav bitstream into a text file.
    
    :param input_file: Description
    :type input_file: Path
    :param output_file: Description
    :type output_file: Path
    """
    
    
    with wave.open(str(input_file), "rb") as audio:
        audio_data = audio.readframes(audio.getnframes())

    protected: bool = audio_data.startswith(PROTECTED)
    
    ptr = 0

    if protected:
        ptr += 1
        salt = audio_data[ptr:ptr+16]
        ptr += 16
        entered_pass = typer.prompt("The file you want to decode is protected with a password.\nPassword", hide_input=True)

        fernet = get_fernet(entered_pass, salt)  

    if audio_data.startswith(DIR_START):
        if not output.exists():
            output.mkdir(parents=True)

        with console.status("[bold green]Decoding audio") as status:
            while ptr < len(audio_data):
                marker = audio_data[ptr:ptr+1]
                ptr += 1

                # Read Name
                name_len = struct.unpack(">I", audio_data[ptr:ptr+4])[0]
                ptr += 4
                name = audio_data[ptr:ptr+name_len].decode('utf-8')
                ptr += name_len

                target_path = output / name
                
                if marker == DIR_START:
                    target_path.mkdir(parents=True, exist_ok=True)
                elif marker == FILE_START:
                    # Read Content
                    content_len = struct.unpack(">I", audio_data[ptr:ptr+4])[0]
                    ptr += 4
                    content = audio_data[ptr:ptr+content_len]
                    ptr += content_len

                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    target_path.write_bytes(content)
    else:
        # Single File
        if protected:
            try:
                decrypted_data = fernet.decrypt(audio_data[ptr::])
            except InvalidToken:
                typer.secho(f"Access Denied! Wrong password entered.", fg=typer.colors.RED)
                raise typer.Exit()       
            
            output.write_bytes(decrypted_data)
        else:
            output.write_bytes(audio_data[ptr::])

    typer.secho(f"Converted {input_file} -> {output}", fg=typer.colors.GREEN)

if __name__ == "__main__":
    app()