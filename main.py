import base64
import io
import logging
import os

from ollama import Client
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

bot_token = os.environ['APIKEY']
llm_endpoint = os.environ['LLM_ENDPOINT']
llm_model = os.environ['LLM_MODEL']
system_prompt = os.environ['LLM_PROMPT']
think_message = os.environ['THINK_MESSAGE']
bot_name = os.environ['BOT_NAME']
bot_nick = os.environ['BOT_NICK']

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

client = Client(
    host=llm_endpoint,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Received /start command.")
    chat_id = update.message.chat_id
    await context.bot.send_message(chat_id=chat_id,
                                   text="Hi")


async def ask_mao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Received /ask mao command.")
    chat_id = update.message.chat_id
    message = update.message.text
    logging.info(f"Text request is: {message}")
    message = message.replace(f"/{bot_name}@{bot_nick}", '')
    message = message.replace(f'/{bot_name}', '')

    logging.info(f"Text request is: {message}")
    if message == "" and update.message.reply_to_message is None:
        await context.bot.send_message(chat_id=chat_id, text="waiting for questions.")
        return
    else:
        await context.bot.send_message(chat_id=chat_id, text=think_message)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    if update.message.reply_to_message:
        logging.info("Creating response including reply.")
        if update.message.reply_to_message.photo:
            logging.info(f"Reply to an image: {message}")
            photo = update.message.reply_to_message.photo[-1]
            file = await get_file_from_message(photo, context)
            mao_response = get_response_for_image(update.message.text, file)
        else:
            logging.info(f"Reply to a text: {message}")
            mao_response = get_response(
                f'{update.message.text}: message from another user {update.message.reply_to_message.from_user.first_name} - {update.message.reply_to_message.text}')
    else:
        logging.info("Creating direct response.")
        if update.message.photo:
            photo = update.message.photo[-1]
            file = await get_file_from_message(photo, context)
            mao_response = get_response_for_image(update.message.text, file)
        else:
            mao_response = get_response(update.message.text)

    await context.bot.send_message(chat_id=chat_id, reply_to_message_id=update.message.id,
                                   text=mao_response)


async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    message = update.message
    if message.reply_to_message:
        if message.reply_to_message.from_user.id == context.bot.id:
            logging.info("Reply to a bot message without command.")
            await context.bot.send_message(chat_id=chat_id, text=think_message)
            mao_response = get_response_for_reply(update.message.text, update.message.reply_to_message.text)
            await message.reply_text(mao_response)


async def get_file_from_message(file, context):
    file_id = file.file_id
    file = await context.bot.get_file(file_id)
    f = io.BytesIO()
    await file.download_to_memory(out=f)
    return f


def get_response(user_input):
    return client.chat(model=llm_model, messages=[
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            'role': 'user',
            'content': f'{user_input}',
            'stream': 'false'
        },
    ])['message']['content']


def get_response_for_reply(user_input, previous_mao_response):
    return client.chat(model=llm_model, messages=[
        {
            "role": "system",
            "content": system_prompt,
        }
        ,
        {
            "role": "assistant",
            'content': f'{previous_mao_response}',
            'stream': 'false'
        }
        ,
        {
            'role': 'user',
            'content': f'{user_input}',
            'stream': 'false'
        },
    ])['message']['content']


def get_response_for_image(user_input, image):
    base64_image = base64.b64encode(image.read())
    if user_input == "":
        user_input = "Describe image"
    logging.info(f"User input is {user_input}.")

    return client.chat(model=llm_model, messages=[
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            'role': 'user',
            'content': f'{user_input}',
            'stream': 'false',
            "images": base64_image
        },
    ])['message']['content']


if __name__ == '__main__':
    logging.info("Starting Telegram bot...")

    application = ApplicationBuilder().token(bot_token).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler(bot_name, ask_mao))
    application.add_handler(MessageHandler(filters.REPLY & ~filters.COMMAND, handle_reply))

    application.run_polling()
