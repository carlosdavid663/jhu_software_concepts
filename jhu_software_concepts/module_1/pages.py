from flask import Blueprint, render_template

# the blueprint keeps our page routes together in one file.
pages = Blueprint("pages", __name__)


# Show the home page when someone visits the main address.
@pages.route("/")
def home():
    return render_template("home.html", title="About", current_page="home")


# Show the projects page when someone visits projects.
@pages.route("/projects")
def projects():
    return render_template("projects.html", title="Projects", current_page="projects")


# Show the contact page when someone visits contact.
@pages.route("/contact")
def contact():
    return render_template("contact.html", title="Contact", current_page="contact")
