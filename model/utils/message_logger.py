import os
import json
from google.protobuf.json_format import MessageToDict

class MessageLogger:
    def __init__(self, mode: str, target_folder: str="") -> None:
        self.mode = mode
        if os.path.isdir(target_folder):
            self.target_folder = target_folder
            self.delete_old_files()
        else:
            raise Exception('logging folder does not exist.')
        
    def delete_old_files(self):
        for filename in os.listdir(self.target_folder):
            file_path = os.path.join(self.target_folder, filename)
            try:
                if (os.path.isfile(file_path) or os.path.islink(file_path)) and filename[-4:] == ".RAW":
                   os.unlink(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))


    def log_message(self, message, pdata=None, handled=False, raw:bytes=None, prefix: str=None, title: str=None):
        if self.mode == "none" or (self.mode == "unhandled" and handled):
            return
        if type(message) == bytes:
            file_name = "binary.RAW"
        elif type(message) == dict:
            # JSON 
            if 'cmdFunc' in message and 'cmdId' in message:
                file_name = f"{message['cmdFunc']}-{message['cmdId']}.RAW"
            else:
                file_name = "json.RAW"
        else:
            file_name = f"{message.cmd_func}-{message.cmd_id}.RAW"
        if prefix is not None:
            file_name = f"{prefix.replace(' ', '_')}_{file_name}"
        with open(os.path.join(self.target_folder, file_name), "w") as f:
            if title is not None:
                f.write(f"{title}:\n")
            if raw is not None:
                if type(raw) == bytes:
                    f.write("RAW: %s\n" % raw.hex())
                elif type(raw) == str:
                    f.write("RAW: %s\n" % raw)
            message_dict = {}
            if type(message) == bytes:
                message_dict["raw"] = message.hex()
            elif type(message) == dict:
                message_dict = message
            else:
                message_dict = MessageToDict(message)
                
            if pdata is not None:
                if type(pdata) == bytes:
                    message_dict["pdata"] = pdata.hex()
                else:
                    message_dict["pdata"] = MessageToDict(pdata)

            f.write(f"{json.dumps(message_dict, indent=4)}")
            f.write("\n")