            if (session.get('phase') != 'listening' or session.get('input_active')
                    or session.get('quiet_ms', 0) < 4000 or session.get('pending')
                    or len(self.notices) >= self.MAX_NOTICES
                    or (self.notices and self.clock()-self.notices[-1] < self.NOTICE_SECONDS)):
                return None
