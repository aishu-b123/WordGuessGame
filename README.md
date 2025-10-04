# Guess the Word Game 

## Project Overview
"Guess the Word" is an interactive word-guessing game developed with **Python, Flask, and MySQL**.  
The game allows users to register, log in, and guess a randomly selected 5-letter word from a database.  
There are two types of users:

- **Admin**: Configure game settings, run reports, and monitor user activity.  
- **Player**: Play the word-guessing game with a limit of 3 words per day.  


## Features

### User Registration & Login
- Username: Minimum 5 letters (supports both upper and lower case).  
- Password: Minimum 5 characters, must include alphabets, numbers, and one special character (`$`, `%`, `*`, `@`).  
- Users can securely register and log in.

### Game Rules
- Start a game by randomly selecting a 5-letter word from the database.  
- Users can guess a word (uppercase only).  
- Maximum **5 guesses per word**.  
- Maximum **3 words per day per user**.  

### Guess Feedback
- **Green**: Correct letter in the correct position.  
- **Orange**: Correct letter in the wrong position.  
- **Grey**: Letter not in the word.  
- Correct guesses display a congratulatory message.  
- If all 5 guesses fail, display a “Better luck next time” message.  

### Data Persistence
- Stores all words in the database (start with 20 5-letter English words).  
- Saves each user's guessed words and attempt history with dates.  

### Admin Reports
- **Daily report**: Number of active users and number of correct guesses.  
- **User report**: Date-wise number of words tried and number of correct guesses.  


## Technologies Used
- **Backend**: Python, Flask  
- **Frontend**: HTML, CSS, JavaScript  
- **Database**: MySQL  
- **Version Control**: Git/GitHub  


