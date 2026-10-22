            with self.lock:
                self.check(epoch)
                if not valid():
                    raise Cancelled()
                with obs.lock:
                    if generation != obs.generation or obs.closed.is_set():
                        raise Cancelled()
                    frame = obs.replace_photo(jpeg)
                self.photo_serial += 1
                frame = Frame(self.photo_serial, frame.jpeg, frame.received, frame.timestamp,
                              'pi', '사용자 요청 후 새 촬영', frame.captured)
                self.last_photo = frame
                return frame

