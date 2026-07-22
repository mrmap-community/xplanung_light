# komserv/settings/test.py – bewusst NICHT in .gitignore, da keine echten Secrets
SECRET_KEY = 'ci-test-key-not-a-real-secret'
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost']