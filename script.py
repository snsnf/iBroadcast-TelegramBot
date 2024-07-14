
import requests
import json
import glob
import os
import hashlib
import sys
import argparse
from concurrent.futures import ThreadPoolExecutor

class ServerError(Exception):
    pass

class Uploader:
    """
    Class for uploading content to iBroadcast.
    """

    VERSION = '0.6'
    CLIENT = 'python 3 uploader script'
    DEVICE_NAME = 'python 3 uploader script'
    USER_AGENT = f'ibroadcast-uploader/{VERSION}'

    def __init__(self, login_token, directory, no_cache, verbose, silent, skip_confirmation, parallel_uploads, playlist, tag, reupload):
        self.login_token = login_token

        if directory:
            os.chdir(directory)

        self.be_verbose = verbose
        self.be_silent = silent
        self.no_cache = no_cache
        self.skip_confirmation = skip_confirmation

        self.user_id = None
        self.token = None
        self.supported = None
        self.files = []
        self.skipped_files = []
        self.failed_files = []
        self.md5_int_path = os.path.expanduser('~/.ibroadcast_md5s')
        self.md5_int = {}
        self.md5_ext = None
        self.reupload = reupload
        self.tag = tag
        self.playlist = playlist
        self.parallel_uploads = parallel_uploads

    def process(self):
        try:
            self.login()
            self.get_supported_types()
            self.load_files()
            if self.confirm():
                self.prepare_upload()
        except (ServerError, ValueError) as e:
            print(f'Error: {e}')

    def login(self):
        if self.be_verbose:
            print('Logging in...')

        post_data = {
            'mode': 'login_token',
            'login_token': self.login_token,
            'app_id': 1007,
            'type': 'account',
            'version': self.VERSION,
            'client': self.CLIENT,
            'device_name': self.DEVICE_NAME,
            'user_agent': self.USER_AGENT
        }
        response = requests.post(
            "https://api.ibroadcast.com/s/JSON/",
            data=json.dumps(post_data),
            headers={'Content-Type': 'application/json', 'User-Agent': self.USER_AGENT}
        )

        if not response.ok:
            raise ServerError(f'Server returned bad status: {response.status_code}')

        jsoned = response.json()

        if 'user' not in jsoned:
            raise ValueError(jsoned.get('message', 'Login failed'))

        self.user_id = jsoned['user']['id']
        self.token = jsoned['user']['token']

        if self.be_verbose:
            print('Login successful - user_id:', self.user_id)

    def get_supported_types(self):
        if self.be_verbose:
            print('Fetching account info...')

        post_data = {
            'mode': 'status',
            'user_id': self.user_id,
            'token': self.token,
            'supported_types': 1,
            'version': self.VERSION,
            'client': self.CLIENT,
            'device_name': self.DEVICE_NAME,
            'user_agent': self.USER_AGENT
        }
        response = requests.post(
            "https://api.ibroadcast.com/s/JSON/",
            data=json.dumps(post_data),
            headers={'Content-Type': 'application/json', 'User-Agent': self.USER_AGENT}
        )

        if not response.ok:
            raise ServerError(f'Server returned bad status: {response.status_code}')

        jsoned = response.json()

        if 'user' not in jsoned:
            raise ValueError(jsoned.get('message', 'Failed to fetch account info'))

        self.supported = [filetype['extension'] for filetype in jsoned.get('supported', [])]

        if self.be_verbose:
            print('Account info fetched')

    def load_files(self, directory=None):
        if self.supported is None:
            raise ValueError('Supported types not set. Have you logged in yet?')

        directory = directory or os.getcwd()

        for full_filename in glob.glob(os.path.join(glob.escape(directory), '*')):
            if os.path.basename(full_filename).startswith('.'):
                continue

            if os.path.isdir(full_filename):
                self.load_files(full_filename)
                continue

            if os.path.splitext(full_filename)[1] in self.supported:
                self.files.append(full_filename)

    def confirm(self):
        if self.skip_confirmation:
            return True

        print(f"Found {len(self.files)} files. Press 'L' to list, or 'U' to start the upload.")
        response = input('--> ').upper()

        if response == 'L':
            print('Listing found, supported files:')
            for filename in sorted(self.files):
                print(' - ', filename)
            print("\nPress 'U' to start the upload if this looks reasonable.")
            response = input('--> ').upper()

        if response == 'U':
            if self.be_verbose:
                print('Starting upload.')
            return True

        if self.be_verbose:
            print('Aborting')
        return False

    def __load_md5_int(self):
        if os.path.exists(self.md5_int_path):
            with open(self.md5_int_path) as json_file:
                self.md5_int = json.load(json_file)
        else:
            self.md5_int = {}

    def __load_md5_ext(self):
        post_data = {
            'user_id': self.user_id,
            'token': self.token
        }
        response = requests.post(
            "https://upload.ibroadcast.com",
            data=post_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

        if not response.ok:
            raise ServerError(f'Server returned bad status: {response.status_code}')

        jsoned = response.json()
        self.md5_ext = jsoned.get('md5', {})

    def calcmd5(self, file_path):
        with open(file_path, 'rb') as fh:
            m = hashlib.md5()
            while chunk := fh.read(8192):
                m.update(chunk)
        return m.hexdigest()

    def check_md5(self):
        self.__load_md5_int()
        self.__load_md5_ext()

        file_list = self.progressbar(self.files, "Calculating MD5 hashes: ", 60) if not self.be_silent and not self.be_verbose else self.files

        for filename in file_list:
            if filename in self.md5_int and not self.no_cache:
                file_md5 = self.md5_int[filename]
            else:
                if not self.be_silent and self.be_verbose:
                    print(f'Calculating MD5 for file "{filename}"... ', end='')
                file_md5 = self.calcmd5(filename)
                self.md5_int[filename] = file_md5

            if file_md5 in self.md5_ext and not self.reupload:
                self.skipped_files.append(filename)
                if not self.be_silent and self.be_verbose:
                    print(f'Skipping "{filename}", already uploaded.')
                self.files.remove(filename)
            elif not self.be_silent and self.be_verbose:
                print(f'The MD5 for "{filename}" is cached, but the file has not been uploaded yet.')

        with open(self.md5_int_path, 'w') as fp:
            json.dump(self.md5_int, fp, indent=2)

    def progressbar(self, it, prefix="", size=60, out=sys.stdout):
        count = len(it)
        def show(j):
            x = int(size * j / count)
            print(f"{prefix}[{'#' * x}{'.' * (size - x)}] {j}/{count}", end='\r', file=out, flush=True)
        if not self.be_silent and not self.be_verbose:
            show(0)
        for i, item in enumerate(it):
            yield item
            if not self.be_silent and not self.be_verbose:
                show(i + 1)
        if not self.be_silent and not self.be_verbose:
            print("\n", flush=True, file=out)

    def prepare_upload(self):
        total_files = len(self.files)
        self.check_md5()
        not_skipped_files = len(self.files)

        if not_skipped_files > 0:
            with ThreadPoolExecutor(max_workers=self.parallel_uploads) as executor:
                for filename in self.files:
                    executor.submit(self.upload, filename)

        skipped = len(self.skipped_files)
        failed = len(self.failed_files)
        uploaded = max(total_files - skipped - failed, 0)
        print(f'Uploaded/Skipped/Failed/Total: {uploaded}/{skipped}/{failed}/{total_files}.')

    def upload(self, filename):
        if not self.be_silent:
            print('Uploading:', filename)

        with open(filename, 'rb') as upload_file:
            file_data = {'file': upload_file}
            post_data = {
                'user_id': self.user_id,
                'token': self.token,
                'file_path': filename,
                'method': self.CLIENT,
                'tag-name': self.tag,
                'playlist-name': self.playlist
            }

            response = requests.post(
                "https://upload.ibroadcast.com",
                data=post_data,
                files=file_data,
            )

            if not response.ok:
                self.failed_files.append(filename)
                raise ServerError(f'Server returned bad status: {response.status_code}')

            jsoned = response.json()
            if not jsoned.get('result', False):
                self.failed_files.append(filename)
                raise ValueError('File upload failed.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run this script in the parent directory of your music files. To acquire a login token, enable the \"Simple Uploaders\" app by visiting https://ibroadcast.com, logging in to your account, and clicking the \"Apps\" button in the side menu.")

    parser.add_argument('login_token', type=str, help='Login token')
    parser.add_argument('directory', type=str, nargs='?', help='Use this directory instead of the current one')
    parser.add_argument('-n', '--no-cache', action='store_true', help='Do not use local MD5 cache')
    parser.add_argument('-v', '--verbose', action='store_true', help='Be verbose')
    parser.add_argument('-p', '--parallel-uploads', type=int, nargs='?', const=3, default=3, choices=range(1, 7), metavar='1-6', help='Number of parallel uploads, 3 by default.')
    parser.add_argument('-s', '--silent', action='store_true', help='Be silent')
    parser.add_argument('-y', '--skip-confirmation', action='store_true', help='Skip confirmation dialogue')
    parser.add_argument('-l', '--playlist', type=str, help='Add uploaded files to this playlist')
    parser.add_argument('-t', '--tag', type=str, help='Apply this tag to the uploaded files')
    parser.add_argument('-r', '--reupload', action='store_true', help='Force re-uploading files')

    args = parser.parse_args()
    uploader = Uploader(args.login_token, args.directory, args.no_cache, args.verbose, args.silent, args.skip_confirmation, args.parallel_uploads, args.playlist, args.tag, args.reupload)
    uploader.process()
