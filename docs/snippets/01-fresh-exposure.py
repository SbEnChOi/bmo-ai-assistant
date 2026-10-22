            # Discard queued frames: exposure must start after this call, not
            # before the user asked for a photograph (Picamera2 flush contract).
            request = self.device.capture_request(flush=True)
            try:
                picture = request.make_image("main").convert("RGB")
            finally:
                request.release()
