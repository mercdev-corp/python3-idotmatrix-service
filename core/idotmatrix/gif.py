import io
import logging
from PIL import Image as PilImage, GifImagePlugin
import zlib

GifImagePlugin.LOADING_STRATEGY = GifImagePlugin.LoadingStrategy.RGB_AFTER_DIFFERENT_PALETTE_ONLY


class Gif:
    logging = logging.getLogger("idotmatrix." + __name__)

    def load_gif(self, file_path):
        """Load a gif file into a byte buffer.

        Args:
            file_path (str): path to file

        Returns:
            file: returns the file contents
        """
        with open(file_path, "rb") as file:
            return file.read()

    def split_into_chunks(self, data, chunk_size):
        """Split the data into chunks of specified size.

        Args:
            data (bytearray): data to split into chunks
            chunk_size (int): size of the chunks

        Returns:
            list: returns list with chunks of given data input
        """
        return [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]

    def create_payloads(self, gif_data):
        """Creates payloads from a GIF file.

        Args:
            gif_data (bytearray): data of the gif file

        Returns:
            list: returns list of 4096-byte chunk payloads
        """
        # Calculate CRC of the GIF data
        crc = zlib.crc32(gif_data)
        # header for gif (16 bytes)
        # Protocol:
        # [0:2]   Chunk length including 16-byte header (uint16 LE)
        # [2]     Data type: 1 = GIF
        # [3]     Subtype: 0
        # [4]     Option: 0 for 1st chunk, 2 for subsequent chunks
        # [5:9]   Total GIF payload size across all chunks (uint32 LE)
        # [9:13]  CRC32 of GIF payload (uint32 LE)
        # [13:15] Time sign / duration: 5 seconds (uint16 LE = 0x05, 0x00)
        # [15]    Image index: 13 (0x0D) = preview / DIY live animation buffer
        header = bytearray(
            [
                0,
                0,
                1,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                5,
                0,
                13,
            ]
        )
        # Set total length of the GIF data (bytes 5..8, Little Endian 4 bytes)
        # Protocol specification: exact length of the GIF data (excluding headers)
        header[5:9] = int(len(gif_data)).to_bytes(4, byteorder="little")
        # Add CRC32 (bytes 9..12, Little Endian 4 bytes)
        header[9:13] = crc.to_bytes(4, byteorder="little")
        # Split the GIF data into 4096-byte chunks
        gif_chunks = self.split_into_chunks(gif_data, 4096)
        # Build chunk payloads
        chunks = []
        for i, chunk in enumerate(gif_chunks):
            chunk_header = bytearray(header)
            chunk_header[4] = 2 if i > 0 else 0
            chunk_len = len(chunk) + len(header)
            chunk_header[0:2] = chunk_len.to_bytes(2, byteorder="little")
            chunks.append(chunk_header + chunk)
        return chunks

    def upload_unprocessed(self, file_path):
        """uploads an image without further checks and resizes.

        Args:
            file_path (str): path to the image file

        Returns:
            list: returns list of chunk payloads
        """
        gif_data = self.load_gif(file_path)
        return self.create_payloads(gif_data)

    def upload_processed(self, file_path=None, pixel_size=32, file=None):
        """uploads a file processed to make sure everything is correct before uploading to the device.

        Args:
            file_path (str, optional): path to the image file
            pixel_size (int, optional): amount of pixels (either 16 or 32 makes sense). Defaults to 32.
            file (str, optional): alias for file_path for compatibility.

        Returns:
            list: returns list of chunk payloads
        """
        target_file = file_path or file
        if not target_file:
            self.logging.error("No file provided for upload_processed")
            return []
        try:
            # Open the gif file
            with PilImage.open(target_file) as img:
                frames = []
                durations = []
                try:
                    while True:
                        frame = img.copy()
                        if frame.size != (pixel_size, pixel_size):
                            # Resize the current frame
                            frame = frame.resize(
                                (pixel_size, pixel_size), PilImage.Resampling.NEAREST
                            )
                        # Ensure frame has proper RGB / P conversion
                        if frame.mode == "RGBA":
                            bg = PilImage.new("RGB", (pixel_size, pixel_size), (0, 0, 0))
                            bg.paste(frame, mask=frame.split()[3])
                            frame = bg
                        elif frame.mode != "RGB" and frame.mode != "P":
                            frame = frame.convert("RGB")

                        frame = frame.convert("P", palette=PilImage.Palette.ADAPTIVE, colors=256)
                        frames.append(frame)

                        frame_dur = frame.info.get("duration", img.info.get("duration", 100))
                        durations.append(frame_dur if frame_dur and frame_dur > 0 else 100)
                        # Move to the next frame
                        img.seek(img.tell() + 1)
                except EOFError:
                    pass  # End of sequence

                if not frames:
                    self.logging.error("No frames found in image")
                    return []

                # Limit to 64 frames max to prevent memory exhaustion on device firmware
                if len(frames) > 64:
                    step = len(frames) / 64
                    selected_indices = [int(i * step) for i in range(64)]
                    frames = [frames[i] for i in selected_indices]
                    durations = [durations[i] for i in selected_indices]

                # Create a BytesIO object to hold the GIF data
                gif_buffer = io.BytesIO()
                duration = durations[0] if len(durations) == 1 else durations
                # Save the resized image as GIF with infinite loop (loop=0) and original durations
                frames[0].save(
                    gif_buffer,
                    format="GIF",
                    save_all=True,
                    append_images=frames[1:],
                    loop=0,
                    duration=duration,
                    disposal=2,
                    optimize=True,
                )
                # Seek to the start of the GIF buffer
                gif_buffer.seek(0)
                # Return the GIF chunk payloads
                return self.create_payloads(gif_buffer.getvalue())
        except Exception as e:
            self.logging.error("could not process gif: {}".format(e))
            return []
