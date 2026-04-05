from main import app, initialize_database, db
from routes import auth_bp, customer_bp, plumber_bp, admin_bp, notification_bp


app.register_blueprint(auth_bp)
app.register_blueprint(customer_bp)
app.register_blueprint(plumber_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(notification_bp)


if __name__ == "__main__":
    initialize_database()
    app.run(host="127.0.0.1", port=5000, debug=True)
