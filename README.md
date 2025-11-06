# Job Portal System

A comprehensive job portal web application built with Flask, MongoDB, and Bootstrap.

## Features

### User Roles
- **Job Seekers**: Browse jobs, apply, manage profile and resume
- **Employers**: Post jobs, manage applications, update statuses
- **Admin**: Manage users, jobs, applications, and analytics

### Technical Features
- User authentication and role-based access
- Resume upload using GridFS
- Email notifications
- Data analytics and visualizations
- Responsive UI with Bootstrap

## Tech Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript (Bootstrap)
- **Database**: MongoDB
- **Data Processing**: NumPy, Pandas
- **Visualization**: Matplotlib, Seaborn
- **File Storage**: MongoDB GridFS
- **Email**: Flask-Mail

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up MongoDB locally (ensure it's running on `mongodb://localhost:27017/`)
5. Create a `.env` file based on the example in the project
6. Run the application:
   ```bash
   python app.py
   ```

## Configuration

Create a `.env` file with the following variables:

```env
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your_secret_key_here
MONGO_URI=mongodb://localhost:27017/job_portal_db

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password

UPLOAD_FOLDER=uploads
PLOTS_FOLDER=static/plots
ALLOWED_EXTENSIONS=pdf,doc,docx,png,jpg,jpeg
```

## Usage

1. Start the MongoDB service
2. Run the Flask application: `python app.py`
3. Access the application at `http://localhost:5000`
4. Register as a new user or use existing credentials
5. Use the role-based dashboards to manage jobs or applications

## Database Schema

- `users`: { _id, name, email, password, role, profile, resume_id }
- `job_posts`: { _id, title, description, requirements, salary, category, location, employer_id, date_posted }
- `applications`: { _id, job_id, job_seeker_id, status, date_applied }
- Resumes are stored in GridFS

## Project Structure

```
job_portal/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── .env                   # Configuration variables
├── templates/             # HTML templates
│   ├── base.html          # Base template
│   ├── login.html         # Login page
│   ├── register.html      # Registration page
│   ├── index.html         # Home page
│   ├── job_seeker_dashboard.html
│   ├── employer_dashboard.html
│   ├── admin_dashboard.html
│   ├── admin_analytics.html
│   ├── post_job.html
│   ├── profile.html
│   └── view_applicant.html
├── static/                # Static assets
│   ├── css/
│   ├── js/
│   ├── plots/             # Generated charts
│   └── uploads/           # Temporary uploads
└── uploads/
```