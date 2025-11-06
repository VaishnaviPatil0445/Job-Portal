from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from pymongo import MongoClient
from gridfs import GridFS
import os
from datetime import datetime
import numpy as np
import pandas as pd
# Set matplotlib backend to 'Agg' before importing pyplot to avoid GUI issues in web app
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import base64
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config['MONGO_URI'] = os.getenv("MONGO_URI")
app.config['UPLOAD_FOLDER'] = os.getenv("UPLOAD_FOLDER")
app.config['PLOTS_FOLDER'] = os.getenv("PLOTS_FOLDER")

# Flask-Mail Config
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS') == 'True'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL') == 'True'  # Added SSL config
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

# Initialize extensions
mongo = PyMongo(app)
mail = Mail(app)

# Initialize GridFS
client = MongoClient(os.getenv("MONGO_URI"))
db = client.job_portal_db
fs = GridFS(db)

# Allowed file extensions
ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", "").split(','))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_email(to, subject, body):
    try:
        msg = Message(
            subject, 
            sender=(app.config['MAIL_USERNAME'], 'Job Portal'),  # Set sender name as 'Job Portal'
            recipients=[to]
        )
        msg.body = body
        msg.html = f"<p>{body.replace(chr(10), '<br>')}</p>"  # Convert newlines to HTML line breaks
        mail.send(msg)
        print(f"Email sent successfully to: {to}, Subject: {subject}")  # Debug print
        return True
    except Exception as e:
        print(f"Error sending email to {to}: {str(e)}")
        return False

@app.route('/')
def index():
    if 'user_id' in session:
        user = mongo.db.users.find_one({'_id': session['user_id']})
        if user:
            if user['role'] == 'job_seeker':
                return redirect(url_for('job_seeker_dashboard'))
            elif user['role'] == 'employer':
                return redirect(url_for('employer_dashboard'))
            elif user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        
        # Basic validation
        if not name or not email or not password or not role:
            flash('All fields are required!')
            return render_template('register.html')
        
        # Check if user already exists
        existing_user = mongo.db.users.find_one({'email': email})
        if existing_user:
            flash('User with this email already exists!')
            return render_template('register.html')
        
        # Validate the role
        valid_roles = ['job_seeker', 'employer', 'admin']
        if role not in valid_roles:
            flash('Invalid role selected!')
            return render_template('register.html')
        
        # Hash password and create user
        hashed_password = generate_password_hash(password)
        user_data = {
            'name': name,
            'email': email,
            'password': hashed_password,
            'role': role
        }
        
        result = mongo.db.users.insert_one(user_data)
        flash('Registration successful!')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Find user
        user = mongo.db.users.find_one({'email': email})
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['_id']
            session['role'] = user['role']
            session['name'] = user['name']
            
            if user['role'] == 'job_seeker':
                return redirect(url_for('job_seeker_dashboard'))
            elif user['role'] == 'employer':
                return redirect(url_for('employer_dashboard'))
            elif user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                # Handle unexpected roles
                flash('Invalid user role. Please contact admin.')
                return redirect(url_for('login'))
        else:
            flash('Invalid email or password!')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/job_seeker/dashboard')
def job_seeker_dashboard():
    if 'user_id' not in session or session.get('role') != 'job_seeker':
        return redirect(url_for('login'))
    
    # Get the current user
    user = mongo.db.users.find_one({'_id': session['user_id']})
    
    # Get query parameters for search and filter
    search_query = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    location = request.args.get('location', '').strip()
    min_salary = request.args.get('min_salary', '').strip()
    
    # Build query for filtering jobs
    query = {}
    
    # Search query - search in title, company name, description, and requirements
    if search_query:
        query['$or'] = [
            {'title': {'$regex': search_query, '$options': 'i'}},
            {'company_name': {'$regex': search_query, '$options': 'i'}},
            {'description': {'$regex': search_query, '$options': 'i'}},
            {'requirements': {'$regex': search_query, '$options': 'i'}}
        ]
    
    # Category filter
    if category:
        query['category'] = category
    
    # Location filter
    if location:
        query['location'] = {'$regex': location, '$options': 'i'}
    
    # Minimum salary filter
    if min_salary and min_salary.isdigit():
        query['salary'] = {'$gte': float(min_salary)}
    
    # Get filtered job posts
    jobs = list(mongo.db.job_posts.find(query))
    
    # Get user's applications
    applications = list(mongo.db.applications.find({'job_seeker_id': session['user_id']}).sort('date_applied', -1))
    
    # Join with job details
    for app in applications:
        job = mongo.db.job_posts.find_one({'_id': app['job_id']})
        if job:
            app['job_title'] = job['title']
            app['company'] = job.get('company_name', 'Unknown')
    
    return render_template('job_seeker_dashboard.html', jobs=jobs, filtered_jobs=jobs, applications=applications, user=user)

@app.route('/employer/dashboard')
def employer_dashboard():
    if 'user_id' not in session or session.get('role') != 'employer':
        return redirect(url_for('login'))
    
    # Get jobs posted by this employer
    jobs = list(mongo.db.job_posts.find({'employer_id': session['user_id']}))
    
    # Count applications for each job
    for job in jobs:
        job['applications_count'] = mongo.db.applications.count_documents({'job_id': job['_id']})
    
    # Get all applications for these jobs
    job_ids = [job['_id'] for job in jobs]
    applications = []
    if job_ids:
        applications = list(mongo.db.applications.find({'job_id': {'$in': job_ids}}).sort('date_applied', -1))
        
        # Join with job seeker details
        for app in applications:
            job_seeker = mongo.db.users.find_one({'_id': app['job_seeker_id']})
            if job_seeker:
                app['job_seeker_name'] = job_seeker['name']
                app['job_seeker_email'] = job_seeker['email']
            
            job = mongo.db.job_posts.find_one({'_id': app['job_id']})
            if job:
                app['job_title'] = job['title']
    
    return render_template('employer_dashboard.html', jobs=jobs, applications=applications)

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # Get counts for dashboard
    total_users = mongo.db.users.count_documents({})
    total_job_posts = mongo.db.job_posts.count_documents({})
    total_applications = mongo.db.applications.count_documents({})
    
    # Get recent activity
    recent_users = list(mongo.db.users.find().sort('_id', -1).limit(5))
    recent_jobs = list(mongo.db.job_posts.find().sort('_id', -1).limit(5))
    recent_applications = list(mongo.db.applications.find().sort('_id', -1).limit(5))
    
    # Generate visualizations
    plot_paths = generate_admin_plots()
    
    return render_template('admin_dashboard.html', 
                          total_users=total_users,
                          total_job_posts=total_job_posts,
                          total_applications=total_applications,
                          recent_users=recent_users,
                          recent_jobs=recent_jobs,
                          recent_applications=recent_applications,
                          plot_paths=plot_paths)

def generate_admin_plots():
    """Generate admin dashboard visualizations"""
    plots = {}
    
    # Bar Chart - Job count per category
    try:
        jobs = list(mongo.db.job_posts.find({}, {'category': 1}))
        categories = [job['category'] for job in jobs if 'category' in job]
        
        if categories:
            df = pd.DataFrame(categories, columns=['category'])
            category_counts = df['category'].value_counts()
            
            plt.figure(figsize=(10, 6))
            plt.bar(category_counts.index, category_counts.values)
            plt.title('Job Count per Category')
            plt.xlabel('Category')
            plt.ylabel('Count')
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            plot_path = os.path.join(app.config['PLOTS_FOLDER'], 'job_categories.png')
            plt.savefig(plot_path)
            plt.close()
            
            plots['job_categories'] = plot_path
    except Exception as e:
        print(f"Error generating job categories plot: {str(e)}")
    
    # Pie Chart - Application status distribution
    try:
        applications = list(mongo.db.applications.find({}, {'status': 1}))
        statuses = [app['status'] for app in applications if 'status' in app]
        
        if statuses:
            df = pd.DataFrame(statuses, columns=['status'])
            status_counts = df['status'].value_counts()
            
            plt.figure(figsize=(8, 6))
            plt.pie(status_counts.values, labels=status_counts.index, autopct='%1.1f%%')
            plt.title('Application Status Distribution')
            plt.tight_layout()
            
            plot_path = os.path.join(app.config['PLOTS_FOLDER'], 'application_status.png')
            plt.savefig(plot_path)
            plt.close()
            
            plots['application_status'] = plot_path
    except Exception as e:
        print(f"Error generating application status plot: {str(e)}")
    
    # Line Chart - Applications over time
    try:
        applications = list(mongo.db.applications.find({}, {'date_applied': 1, 'status': 1}))
        dates = [app['date_applied'].strftime('%Y-%m-%d') for app in applications if 'date_applied' in app]
        
        if dates:
            df = pd.DataFrame(dates, columns=['date'])
            date_counts = df['date'].value_counts().sort_index()
            
            plt.figure(figsize=(10, 6))
            plt.plot(date_counts.index, date_counts.values, marker='o')
            plt.title('Applications Over Time')
            plt.xlabel('Date')
            plt.ylabel('Number of Applications')
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            plot_path = os.path.join(app.config['PLOTS_FOLDER'], 'applications_over_time.png')
            plt.savefig(plot_path)
            plt.close()
            
            plots['applications_over_time'] = plot_path
    except Exception as e:
        print(f"Error generating applications over time plot: {str(e)}")
    
    # Histogram - Salary distribution
    try:
        jobs = list(mongo.db.job_posts.find({}, {'salary': 1}))
        salaries = [job['salary'] for job in jobs if 'salary' in job and job['salary'] is not None]
        
        if salaries:
            plt.figure(figsize=(10, 6))
            plt.hist(salaries, bins=20, edgecolor='black')
            plt.title('Salary Distribution')
            plt.xlabel('Salary')
            plt.ylabel('Frequency')
            plt.tight_layout()
            
            plot_path = os.path.join(app.config['PLOTS_FOLDER'], 'salary_distribution.png')
            plt.savefig(plot_path)
            plt.close()
            
            plots['salary_distribution'] = plot_path
    except Exception as e:
        print(f"Error generating salary distribution plot: {str(e)}")
    
    # Bar Chart - Most active employers
    try:
        # Count jobs per employer
        pipeline = [
            {
                '$group': {
                    '_id': '$employer_id',
                    'job_count': {'$sum': 1}
                }
            },
            {
                '$sort': {'job_count': -1}
            },
            {
                '$limit': 10
            }
        ]
        
        employer_counts = list(mongo.db.job_posts.aggregate(pipeline))
        
        if employer_counts:
            # Get employer names
            employer_ids = [emp['_id'] for emp in employer_counts]
            employers = list(mongo.db.users.find({'_id': {'$in': employer_ids}}, {'name': 1}))
            employer_names = {emp['_id']: emp['name'] for emp in employers}
            
            employer_labels = [employer_names.get(emp['_id'], str(emp['_id'])) for emp in employer_counts]
            job_counts = [emp['job_count'] for emp in employer_counts]
            
            plt.figure(figsize=(10, 6))
            plt.bar(employer_labels, job_counts)
            plt.title('Top 10 Most Active Employers')
            plt.xlabel('Employer')
            plt.ylabel('Number of Jobs Posted')
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            plot_path = os.path.join(app.config['PLOTS_FOLDER'], 'top_employers.png')
            plt.savefig(plot_path)
            plt.close()
            
            plots['top_employers'] = plot_path
    except Exception as e:
        print(f"Error generating top employers plot: {str(e)}")
    
    return plots

@app.route('/admin/analytics')
def admin_analytics():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # Calculate additional analytics
    pipeline = [
        {
            '$group': {
                '_id': '$category',
                'avg_salary': {'$avg': '$salary'},
                'count': {'$sum': 1}
            }
        }
    ]
    
    category_analytics = list(mongo.db.job_posts.aggregate(pipeline))
    
    # Calculate overall average salary
    overall_avg_salary = 0
    if category_analytics:
        total_salary = sum(cat['avg_salary'] for cat in category_analytics)
        overall_avg_salary = total_salary / len(category_analytics)
    
    # Get user counts by role
    user_counts = {}
    for role in ['job_seeker', 'employer']:
        user_counts[role] = mongo.db.users.count_documents({'role': role})
    
    plot_paths = generate_admin_plots()
    
    return render_template('admin_analytics.html', 
                          category_analytics=category_analytics, 
                          user_counts=user_counts,
                          overall_avg_salary=overall_avg_salary,
                          plot_paths=plot_paths)

@app.route('/post_job', methods=['GET', 'POST'])
def post_job():
    if 'user_id' not in session or session.get('role') != 'employer':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        requirements = request.form['requirements']
        salary = float(request.form['salary'])
        category = request.form['category']
        location = request.form['location']
        company_name = request.form['company_name']
        company_address = request.form['company_address']
        company_website = request.form.get('company_website', '')
        contact_person = request.form.get('contact_person', '')
        contact_email = request.form.get('contact_email', '')
        contact_phone = request.form.get('contact_phone', '')
        employer_id = session['user_id']
        
        job_data = {
            'title': title,
            'description': description,
            'requirements': requirements,
            'salary': salary,
            'category': category,
            'location': location,
            'company_name': company_name,
            'company_address': company_address,
            'company_website': company_website,
            'contact_person': contact_person,
            'contact_email': contact_email,
            'contact_phone': contact_phone,
            'employer_id': employer_id,
            'date_posted': datetime.utcnow()
        }
        
        mongo.db.job_posts.insert_one(job_data)
        flash('Job posted successfully!')
        return redirect(url_for('employer_dashboard'))
    
    return render_template('post_job.html')

@app.route('/apply_job/<job_id>', methods=['POST'])
def apply_job(job_id):
    if 'user_id' not in session or session.get('role') != 'job_seeker':
        return redirect(url_for('login'))
    
    from bson import ObjectId
    try:
        job_object_id = ObjectId(job_id)
    except:
        flash('Invalid job ID')
        return redirect(url_for('job_seeker_dashboard'))
    
    # Get the current user's profile
    user = mongo.db.users.find_one({'_id': session['user_id']})
    
    # Check if the user has a complete profile and resume
    profile_complete = True
    if not user.get('profile'):
        profile_complete = False
    elif not user['profile'].get('education') or not user['profile'].get('experience') or not user['profile'].get('skills'):
        profile_complete = False
    
    # Check if user has uploaded a resume
    if not user.get('resume_id'):
        profile_complete = False
    
    if not profile_complete:
        flash('Please complete your profile and upload a resume before applying for jobs.')
        return redirect(url_for('profile'))
    
    # Check if already applied
    existing_application = mongo.db.applications.find_one({
        'job_id': job_object_id,
        'job_seeker_id': session['user_id']
    })
    
    if existing_application:
        flash('You have already applied for this job!')
        return redirect(url_for('job_seeker_dashboard'))
    
    application_data = {
        'job_id': job_object_id,
        'job_seeker_id': session['user_id'],
        'status': 'Pending',
        'date_applied': datetime.utcnow()
    }
    
    result = mongo.db.applications.insert_one(application_data)
    
    # Send confirmation email to job seeker
    job = mongo.db.job_posts.find_one({'_id': job_object_id})
    user = mongo.db.users.find_one({'_id': session['user_id']})
    
    if job and user:
        # Email to job seeker
        subject = f"Application Received for {job['title']}"
        body = f"Dear {user['name']},\n\nYour application for the position \"{job['title']}\" has been received successfully.\n\nApplication ID: {str(result.inserted_id)}\nApplied on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\nStatus: Pending\n\nWe will notify you once the employer reviews your application.\n\nBest regards,\nJob Portal Team"
        
        send_email(user['email'], subject, body)
        
        # Email to employer about new application
        employer = mongo.db.users.find_one({'_id': job['employer_id']})
        if employer:
            emp_subject = f"New Application for {job['title']}"
            emp_body = f"Dear {employer['name']},\n\nYou have received a new application for the position \"{job['title']}\".\n\nApplicant: {user['name']}\nEmail: {user['email']}\nApplication ID: {str(result.inserted_id)}\nApplied on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\nCurrent Status: Pending\n\nPlease review the application in your employer dashboard.\n\nBest regards,\nJob Portal Team"
            
            send_email(employer['email'], emp_subject, emp_body)
    
    flash('Application submitted successfully!')
    return redirect(url_for('job_seeker_dashboard'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session or session.get('role') != 'job_seeker':
        return redirect(url_for('login'))
    
    user = mongo.db.users.find_one({'_id': session['user_id']})
    
    if request.method == 'POST':
        # Update user profile information
        name = request.form.get('name', user['name'])
        email = request.form.get('email', user['email'])
        education = request.form.get('education', '')
        experience = request.form.get('experience', '')
        skills = request.form.get('skills', '')
        
        # Update user document
        mongo.db.users.update_one(
            {'_id': session['user_id']},
            {
                '$set': {
                    'name': name,
                    'email': email,
                    'profile': {
                        'education': education,
                        'experience': experience,
                        'skills': skills
                    }
                }
            }
        )
        
        flash('Profile updated successfully!')
        return redirect(url_for('profile'))
    
    return render_template('profile.html', user=user)

@app.route('/upload_resume', methods=['POST'])
def upload_resume():
    if 'user_id' not in session or session.get('role') != 'job_seeker':
        return redirect(url_for('login'))
    
    if 'resume' not in request.files:
        flash('No file selected')
        return redirect(url_for('profile'))
    
    file = request.files['resume']
    
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('profile'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Store file in GridFS
        file_id = fs.put(file, filename=filename, user_id=session['user_id'])
        
        # Update user document with resume file ID
        mongo.db.users.update_one(
            {'_id': session['user_id']},
            {'$set': {'resume_id': file_id, 'resume_filename': filename}}
        )
        
        flash('Resume uploaded successfully!')
        return redirect(url_for('profile'))
    
    flash('Invalid file type')
    return redirect(url_for('profile'))

@app.route('/download_resume/<user_id>')
def download_resume(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Convert user_id to ObjectId for comparison
    from bson import ObjectId
    
    try:
        user_object_id = ObjectId(user_id)
    except:
        flash('Invalid user ID')
        return redirect(url_for('index'))
    
    # Check if user is admin, employer viewing applicant's resume, or job_seeker viewing own resume
    current_user = mongo.db.users.find_one({'_id': session['user_id']})
    target_user = mongo.db.users.find_one({'_id': user_object_id})
    
    if not target_user:
        flash('User not found')
        if current_user['role'] == 'employer':
            return redirect(url_for('employer_dashboard'))
        else:
            return redirect(url_for('index'))
    
    # Check permissions
    is_authorized = (
        current_user['role'] == 'admin' or  # Admin can access any resume
        (current_user['role'] == 'job_seeker' and str(session['user_id']) == str(user_object_id)) or  # Own resume
        (current_user['role'] == 'employer')  # For simplicity, employers can view any resume in this implementation
    )
    
    if not is_authorized:
        flash('Unauthorized access')
        return redirect(url_for('index'))
    
    if 'resume_id' not in target_user:
        flash('Resume not found')
        if current_user['role'] == 'employer':
            return redirect(url_for('employer_dashboard'))
        else:
            return redirect(url_for('index'))
    
    try:
        # Get file from GridFS
        grid_out = fs.get(target_user['resume_id'])
        return send_file(
            BytesIO(grid_out.read()),
            download_name=target_user.get('resume_filename', 'resume'),
            as_attachment=True
        )
    except Exception as e:
        flash('Error downloading resume')
        if current_user['role'] == 'employer':
            return redirect(url_for('employer_dashboard'))
        else:
            return redirect(url_for('index'))

@app.route('/update_application_status', methods=['POST'])
def update_application_status():
    if 'user_id' not in session or session.get('role') != 'employer':
        return redirect(url_for('login'))
    
    from bson import ObjectId
    try:
        application_id = ObjectId(request.form['application_id'])
    except:
        flash('Invalid application ID')
        return redirect(url_for('employer_dashboard'))
    
    new_status = request.form['status']
    
    # Update application status
    mongo.db.applications.update_one(
        {'_id': application_id},
        {'$set': {'status': new_status}}
    )
    
    # Send email notification to job seeker
    application = mongo.db.applications.find_one({'_id': application_id})
    if application:
        job_seeker = mongo.db.users.find_one({'_id': application['job_seeker_id']})
        job = mongo.db.job_posts.find_one({'_id': application['job_id']})
        
        if job_seeker and job:
            subject = f"Application Status Update for {job['title']}"
            if new_status == 'Accepted':
                body = f"Dear {job_seeker['name']},\n\nGood news! Your application for the position \"{job['title']}\" has been ACCEPTED by the employer.\n\nWe congratulate you and wish you success in your new role!\n\nBest regards,\nJob Portal Team"
            elif new_status == 'Rejected':
                body = f"Dear {job_seeker['name']},\n\nWe regret to inform you that your application for the position \"{job['title']}\" has been REJECTED by the employer.\n\nWe encourage you to keep applying to other opportunities on our platform.\n\nBest regards,\nJob Portal Team"
            else:
                body = f"Dear {job_seeker['name']},\n\nYour application status for the position \"{job['title']}\" has been updated to: {new_status}\n\nApplication Date: {application['date_applied'].strftime('%Y-%m-%d %H:%M:%S')}\n\nBest regards,\nJob Portal Team"
            
            send_email(job_seeker['email'], subject, body)
    
    flash('Application status updated successfully!')
    return redirect(url_for('employer_dashboard'))

@app.route('/view_applicant/<application_id>')
def view_applicant(application_id):
    if 'user_id' not in session or session.get('role') != 'employer':
        return redirect(url_for('login'))
    
    from bson import ObjectId
    try:
        app_object_id = ObjectId(application_id)
    except:
        flash('Invalid application ID')
        return redirect(url_for('employer_dashboard'))
    
    application = mongo.db.applications.find_one({'_id': app_object_id})
    if not application:
        flash('Application not found')
        return redirect(url_for('employer_dashboard'))
    
    job_seeker = mongo.db.users.find_one({'_id': application['job_seeker_id']})
    if not job_seeker:
        flash('Job seeker not found')
        return redirect(url_for('employer_dashboard'))
    
    # Check if the employer has access to this application
    job = mongo.db.job_posts.find_one({'_id': application['job_id']})
    if not job or job['employer_id'] != session['user_id']:
        flash('Unauthorized access')
        return redirect(url_for('employer_dashboard'))
    
    return render_template('view_applicant.html', 
                          application=application, 
                          job_seeker=job_seeker, 
                          job=job)

if __name__ == '__main__':
    app.run(debug=True)