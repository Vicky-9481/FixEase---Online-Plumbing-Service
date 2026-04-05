CREATE TABLE IF NOT EXISTS user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    role VARCHAR(20) NOT NULL DEFAULT 'customer',
    phone VARCHAR(20),
    address VARCHAR(255),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plumber (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    years_of_experience INT NOT NULL,
    charges FLOAT NOT NULL,
    mobile_number VARCHAR(15) NOT NULL,
    license_number VARCHAR(100),
    user_id INT UNIQUE,
    specialties VARCHAR(255),
    availability_status VARCHAR(50) NOT NULL DEFAULT 'available',
    service_area VARCHAR(150),
    bio TEXT,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

CREATE TABLE IF NOT EXISTS request (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    description VARCHAR(500) NOT NULL,
    service_charge FLOAT NOT NULL,
    plumber_id INT,
    status VARCHAR(50) NOT NULL DEFAULT 'requested',
    issue_type VARCHAR(100),
    location VARCHAR(255),
    preferred_date DATE,
    preferred_time VARCHAR(50),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES user(id),
    FOREIGN KEY (plumber_id) REFERENCES plumber(id)
);

CREATE TABLE IF NOT EXISTS notification (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    message TEXT NOT NULL,
    title VARCHAR(150),
    target_url VARCHAR(255),
    request_id INT,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (request_id) REFERENCES request(id)
);

CREATE TABLE IF NOT EXISTS feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NOT NULL UNIQUE,
    customer_id INT NOT NULL,
    plumber_id INT NOT NULL,
    rating INT NOT NULL,
    comment TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES request(id),
    FOREIGN KEY (customer_id) REFERENCES user(id),
    FOREIGN KEY (plumber_id) REFERENCES plumber(id)
);
