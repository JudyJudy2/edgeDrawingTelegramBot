import cv2, requests, random, string, os, shutil, telebot
import numpy as np
from io import BytesIO
from PIL import Image
from time import sleep
import concurrent.futures as futures
import moviepy.editor as mp

author = str(os.environ.get('AUTHOR'))
telegram_bot_token = str(os.environ.get('TOKEN'))
bot = telebot.TeleBot(telegram_bot_token)


@bot.message_handler(commands=['start', 'help'])
def send_welcome(msg):
    bot.reply_to(msg, "Hey! Send me a photo, or a video! \n(Video must be under 10 seconds)")


@bot.message_handler(content_types=["photo"])
def edit_photo(msg):

    bot.reply_to(msg, 'Got it! Give me a sec!')

    try:
        # Get the file info from telegram api and requests, then get the image
        file_info = bot.get_file(msg.photo[-1].file_id)
        r = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(telegram_bot_token, file_info.file_path))

        img = np.array(Image.open(BytesIO(r.content)))

        edges = cv2.Canny(np.array(img), 100, 200)

        # This is really optional. I wait for a little to create a feeling of work for a user.
        sleep(1.5)

        bot.send_photo(msg.chat.id, Image.fromarray(edges))
        bot.send_message(msg.chat.id, 'Done!')

    except Exception as e:
        bot.send_message(msg.chat.id, 'Sorry😢! Something gone wrong in the process⚙'
                                      '\nThe error is: \"{}\"\nPlease report '
                                      'the error to my author, {}!'.format(e, author))


@bot.message_handler(content_types=['video'])
def edit_video(msg):

    bot.reply_to(msg, 'Got it! Wait a few seconds please!')

    try:

        # Get the video file info with telegram api
        file_info = bot.get_file(msg.video.file_id)
        r = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(telegram_bot_token, file_info.file_path))

        # Create a random name for a future files and a folder
        name = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

        open('{}.mp4'.format(name), 'wb').write(r.content)

        # Save the audio separately to add it after
        # because after modifying the video frames - audio record falls out of the video
        video = mp.VideoFileClip('{}.mp4'.format(name))
        video.audio.write_audiofile('{}.mp3'.format(name))
        del video

        video_capture = cv2.VideoCapture('{}.mp4'.format(name))

        fps = video_capture.get(cv2.CAP_PROP_FPS)
        frames = video_capture.get(cv2.CAP_PROP_FRAME_COUNT)
        size = (int(video_capture.get(3)), int(video_capture.get(4)))

        # Check if video is actually under 11 seconds long, if not - it will cause errors
        # because telegram bots are currently limited to 50MB files
        if int(frames / fps) > 11:
            video_capture.release()
            os.remove('{}.mp4'.format(name))
            raise ValueError("The video is not under 10 seconds")

        processes_frames_threads = []
        i = 0

        # Use thread pool executor to speed up the process
        # Use it to modify each file and then save it into a folder one by one
        with futures.ThreadPoolExecutor() as executor:
            while video_capture.isOpened():
                ret, frame = video_capture.read()
                if ret:
                    p = executor.submit(cv2.Canny, np.array(frame), 100, 200, 3)
                    processes_frames_threads.append(p)
                    i += 1
                else:
                    break

            video_capture.release()

            os.mkdir(name)
            [executor.submit(cv2.imwrite(f"{name}/{j}.png", frame.result())) for j, frame in enumerate(processes_frames_threads)]

        # Now we can assemble the video frame by frame
        output_video = cv2.VideoWriter("{}2.mp4".format(name), cv2.VideoWriter_fourcc(*'mp4v'), fps, size)
        [output_video.write(cv2.imread("{}/{}.png".format(name, j))) for j in range(i)]
        output_video.release()

        shutil.rmtree('{}'.format(name))
        os.remove('{}.mp4'.format(name))

        # Modified video does not contain audio, so we are adding it here
        audio_clip = mp.CompositeAudioClip([mp.AudioFileClip("{}.mp3".format(name))])
        video_clip = mp.VideoFileClip("{}2.mp4".format(name))
        video_clip.audio = audio_clip
        video_clip.write_videofile("{}3.mp4".format(name))

        del video_clip
        del video_clip

        os.remove("{}.mp3".format(name))
        os.remove("{}2.mp4".format(name))

        bot.send_video(msg.chat.id, open('{}3.mp4'.format(name), 'rb'))
        bot.send_message(msg.chat.id, 'Done!')

        os.remove('{}3.mp4'.format(name))

    except Exception as e:

        bot.send_message(msg.chat.id, 'Ops.. Something gone wrong! May be try another video. \n\nThe error'
                                      ' was: \"{}\"\nPlease report the error to {} !'.format(e, author))


bot.polling()
