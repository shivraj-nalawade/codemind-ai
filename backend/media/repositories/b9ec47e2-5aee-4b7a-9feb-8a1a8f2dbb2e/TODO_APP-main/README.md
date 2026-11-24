# 📝 Todo Manager

A modern, full-featured task management application built with Django. Stay organized and boost your productivity with an intuitive interface for managing your daily tasks.

---

## ✨ Features

- **👤 User Authentication** - Secure login and registration system
- **✅ Task Management** - Create, edit, mark as complete, and delete tasks
- **📱 Responsive Design** - Beautiful UI that works on all devices
- **🎯 Intuitive Interface** - Simple and user-friendly task management
- **🔒 Secure** - User data protection with session management
- **📊 Status Tracking** - Track completed and pending tasks at a glance

---

## 🛠️ Tech Stack

- **Backend:** Django (Python)
- **Frontend:** HTML, CSS, JavaScript
- **Database:** SQLite (default)
- **Authentication:** Django built-in auth system

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed:
- Python 3.8 or higher
- pip (Python package installer)
- Git

---

## 🚀 Installation & Setup

### 1. Clone the Repository
```bash
git clone <repository-url>
cd DjangoStart
```

### 2. Create Virtual Environment
```bash
python -m venv venv
```

### 3. Activate Virtual Environment

**Windows:**
```bash
venv\Scripts\activate
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Apply Database Migrations
```bash
python manage.py migrate
```

### 6. Create Superuser (Admin)
```bash
python manage.py createsuperuser
```

### 7. Run Development Server
```bash
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`

---

## 📖 Usage

### Getting Started
1. **Register** - Create a new account or login with existing credentials
2. **Add Tasks** - Create new tasks from the main dashboard
3. **Manage Tasks** - Mark tasks as complete or edit them
4. **Delete Tasks** - Remove tasks you no longer need
5. **View Status** - Track your progress at a glance

### Admin Panel
Access the Django admin panel at `/admin` with your superuser credentials to manage:
- Users
- Tasks
- Permissions

---

## 📁 Project Structure

```
DjangoStart/
├── TodoManager/
│   ├── settings.py          # Project settings
│   ├── urls.py              # URL routing
│   ├── wsgi.py              # WSGI configuration
│   └── asgi.py              # ASGI configuration
├── todolist/                # Main app
│   ├── models.py            # Database models
│   ├── views.py             # View logic
│   ├── urls.py              # App URLs
│   ├── forms.py             # Form definitions
│   ├── templates/           # HTML templates
│   │   ├── main.html
│   │   ├── todolist.html
│   │   ├── edit.html
│   │   ├── about.html
│   │   └── contact.html
│   ├── migrations/          # Database migrations
│   └── static/              # Static files
├── users/                   # User authentication app
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   └── templates/
│       ├── login.html
│       ├── register.html
│       └── logout.html
├── static/                  # Global static files
│   ├── css/
│   ├── js/
│   └── image/
├── templates/
│   └── base.html            # Base template
├── manage.py                # Django management script
└── requirements.txt         # Project dependencies
```

---

## 🔧 Configuration

### Settings
Edit `TodoManager/settings.py` to customize:
- Database configuration
- Installed apps
- Middleware
- Static files location
- Allowed hosts

### Environment Variables (Optional)
Create a `.env` file for sensitive data:
```
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

---

## 💾 Database

The project uses SQLite by default. To use a different database:

1. Update `DATABASES` in `settings.py`
2. Install the database adapter (e.g., `psycopg2` for PostgreSQL)
3. Run migrations:
```bash
python manage.py migrate
```

---

## 🧪 Testing

Run the test suite:
```bash
python manage.py test
```

---

## 📝 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Home page |
| `/tasks/` | GET | View all tasks |
| `/tasks/add/` | POST | Create new task |
| `/tasks/<id>/edit/` | POST | Edit task |
| `/tasks/<id>/delete/` | POST | Delete task |
| `/about/` | GET | About page |
| `/contact/` | GET | Contact page |
| `/register/` | GET, POST | User registration |
| `/login/` | GET, POST | User login |
| `/logout/` | GET | User logout |

---

## 🐛 Troubleshooting

### Virtual Environment Issues
```bash
# Recreate virtual environment
deactivate
rmvenv venv
python -m venv venv
venv\Scripts\activate  # Windows
```

### Migration Issues
```bash
# Reset migrations (development only)
python manage.py migrate todolist zero
python manage.py migrate
```

### Port Already in Use
```bash
python manage.py runserver 8001
```

---

## 🤝 Contributing

Contributions are welcome! To contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 👨‍💻 Author

**Your Name** - Initial work

---

## 🙏 Acknowledgments

- Django Documentation
- Django Community
- Contributors and testers

---

## 📞 Support

For support, email support@todoapp.com or open an issue on GitHub.

---

## 🎯 Roadmap

- [ ] Dark mode support
- [ ] Task categories/tags
- [ ] Due dates and reminders
- [ ] Task sharing with other users
- [ ] Mobile app
- [ ] Email notifications

---

**Last Updated:** June 2026

**Status:** ✅ Active Development

