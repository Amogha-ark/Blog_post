from flask import Flask, render_template, url_for, flash, redirect,request,session
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
import yaml
from forms import ArticleForm,RegistrationForm,LoginForm
from functools import wraps
from flask_socketio import SocketIO,send,emit,join_room,leave_room
from time import localtime,strftime

ROOMS = ['ROOM 1','ROOM 2','ROOM 3']

app = Flask(__name__)
bcrypt=Bcrypt()
app.config['SECRET_KEY'] = '5791628bb0b13ce0c676dfde280ba245'
socket = SocketIO(app)

db = yaml.load(open('db.yaml'))

app.config['MYSQL_HOST']=  db['mysql_host']
app.config['MYSQL_USER']= db['mysql_user']
app.config['MYSQL_PASSWORD']= db['mysql_password']
app.config['MYSQL_DB']= db['mysql_db']
mysql=MySQL(app)

def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, *kwargs)
        else:
            flash('Unauthorized, Please login', 'danger')
            return redirect(url_for('login'))
    return wrap

def is_logged_out(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' not in session:
            return f(*args, *kwargs)
            return redirect(url_for('login'))
        else:
            flash('You are Already logged in !', 'success')
            return redirect(url_for('home'))
           
    return wrap




@app.route('/',methods=['GET','POST'])
@app.route('/home',methods=['GET','POST'])
def home():
    cur = mysql.connection.cursor()
    res=cur.execute("select * from articles")
    if res>0:
        articles = cur.fetchall()
        return render_template("home.html",articles = articles)
    
    else:
        flash('No articles found','danger')
    
    return render_template("home.html")


@app.route('/dashboard',methods=['POST','GET'])
@is_logged_in
def dashboard():
    form = ArticleForm()
    if request.method == 'POST' and form.validate_on_submit():
        details = request.form
        title = details['title']
        content = details['body']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO articles(title,body,author) values(%s,%s,%s)",(title,content,session['s_name']))
        mysql.connection.commit()
        cur.close()
        flash(f'Article posted','success')
        return redirect(url_for("home"))
    return render_template("dashboard.html",form=form)


@app.route("/register", methods=['GET', 'POST'])
@is_logged_out
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        if request.method=='POST':
            userdetails=request.form
            username=userdetails['username']
            email=userdetails['email']
            password=userdetails['password']
            hashed_pass=bcrypt.generate_password_hash(password).decode('utf-8')
            cur = mysql.connection.cursor()
            try:
                cur.execute("INSERT INTO users(username,email,password) VALUES(%s,%s,%s)",(username,email,hashed_pass))
            except:
                flash('Username already in use','danger')
                return render_template('register.html',form=form)
            mysql.connection.commit()
            cur.close()
        flash(f'Account created for {form.username.data}!', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', title='Register', form=form)

@app.route("/login", methods=['GET', 'POST'])
@is_logged_out
def login():
    form = LoginForm()
    if form.validate_on_submit():
        if request.method=='POST':
            userdetails=request.form
            email=userdetails['email']
            password=userdetails['password']
            cur = mysql.connection.cursor()
            user=cur.execute("SELECT email FROM users where email= %s",[email])
            if user>0:
                cur.execute("SELECT email,password,username FROM users where email= %s",[email])
                details=cur.fetchone()    #this contains email,password in tuple 
                if bcrypt.check_password_hash(details[1],password):
                    session['logged_in'] = True
                    session['email'] = email
                    session['s_name'] = details[2]
                    flash(f' { details[2] } have been logined successfully!','success')
                    return redirect(url_for('dashboard'))
                else:
                    flash(f'Incorrect password','danger')
            else:
                #pass
                flash(f'Invalid email','danger')
            mysql.connection.commit()
            cur.close()
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route('/logout')
@is_logged_in
def logout():
    if 'logged_in' in session:
        # Create cursor
        session.clear()
        flash('You are logged out', 'success')
        return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))

#Delete Article
@app.route('/delete_article/<string:id>',methods=['POST','GET'])
def delete_article(id):
    cur = mysql.connection.cursor()
    cur.execute("delete from articles where id=%s",[id])
    mysql.connection.commit()
    cur.close()
    flash('Post deleted successfully !!','success')
    return redirect(url_for('home'))

#Edit Article
@app.route('/edit_article/<string:id>',methods=['POST','GET'])
def edit_article(id):
    form = ArticleForm()
    cur = mysql.connection.cursor()
    details = request.form
    cur.execute("select title,body from articles where id=%s",[id])
    res = cur.fetchone()
    #populate the data intially
    form.title.data = res[0]
    form.body.data = res[1]
    #details['body'] = res[1]
    if request.method == 'POST' and form.validate_on_submit():
        
        title = details['title']
        content = details['body']
        
        cur.execute("update articles set title=%s,body=%s where id=%s",[title,content,id])
        mysql.connection.commit()
        cur.close()
        flash(f'Article Updated','success')
        return redirect(url_for("home"))
    return render_template("dashboard.html",form=form)



# chat part of our application


@app.route('/chat',methods=['POST','GET'])
def chat():
    # if request.method == "POST":
    #     print(request.form['umsg'])
    username = session['s_name']
    #room = request.form['room']
    return render_template("chat.html",username=username,rooms=ROOMS)
 
 
@socket.on('message')
def handle_message(data):
    print("message from server")
    
    send({'msg' : data['msg'],'username':data['username'],'time_stamp':strftime('%b-%d %I:%M%p', localtime())},room=data['room'])    
    #emit('user-message','this is custom event')

@socket.on('join')
def join(data):
    join_room(data['room'])
    send({'msg': data['username']+" has joined room "+data['room'] },room=data['room'])
    #emit('join_room_annoucement',data['username']+"has joined room"+data['room'],room=data['room'])

@socket.on('leave')
def leave(data):
    leave_room(data['room'])
    send({'msg': data['username']+" has left room "+data['room'] },room=data['room'])



if __name__=='__main__':
    socket.run(app,debug=True)