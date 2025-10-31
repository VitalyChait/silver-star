# SilverStar

SilverStar is a job application platform that connects experienced professionals with suitable job opportunities. The platform features an AI-powered chatbot that helps candidates find relevant positions based on their skills, preferences, and availability.

## Features

- User authentication and profile management
- AI-powered job recommendations via chatbot
- Voice interaction support for the chatbot
- Job scraping from USAJOBS
- Modern, responsive UI with custom star cursor

## Quick Start

### Configure environment variables
cp code/env_example code/.env"
#### Edit .env with your actual API keys and provider details

### Run scripts/setup_and_run.sh
#### You will be asked if you want to initialize the database
#### You can pass argument to control the ports 


## Accessing the Application

Once running, you can access:

- Main page: http://localhost:NODE_APP_PORT/silverstar.html
- API documentation: http://localhost:PYTHON_APP_PORT/docs

#### Defaults: PYTHON_APP_PORT=8000 , NODE_APP_PORT=3000

