BACKUP_PATH = '/home/ubuntu/MusicBot/data'
input_file_name = 'yti-add-'

todays_date = str(datetime.now().strftime("%m-%d-%y"))
input_file_name = '{base_path}/{file_name}-{date}.pickle'.format(
    base_path=BACKUP_PATH, file_name=input_file_name, date=todays_date)

if os.path.isdir(BACKUP_PATH):
    with open(filename)