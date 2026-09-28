// Login form
//
// API_BASE_URL comes from js/config.js. That file must be loaded before this
// one on every page that includes it.

const API_BASE_URL = window.APP_CONFIG.API_BASE_URL;

const loginForm =
    document.getElementById("loginForm");


function authenticatedJsonHeaders() {
    const token = localStorage.getItem("accessToken");

    return {
        "Content-Type": "application/json",
        ...(token ? { "Authorization": `Bearer ${token}` } : {})
    };
}


if (loginForm) {

    loginForm.addEventListener(
        "submit",
        async function(event) {

            event.preventDefault();


            const email =
                document.getElementById("email").value;

            const password =
                document.getElementById("password").value;

            const loginError =
                document.getElementById("loginError");

            loginError.textContent = "";

            try {
                const response = await fetch(
                    API_BASE_URL + "/auth/login",
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({ email, password })
                    }
                );

                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.detail || "Login failed");
                }

                localStorage.setItem("accessToken", data.access_token);
                localStorage.setItem("userEmail", data.user.email);
                localStorage.setItem("userRole", data.user.role);
                window.location.href = "dashboard.html";
            } catch (error) {
                console.error("Login error:", error);
                loginError.textContent = error.message || "Could not connect to the backend.";
            }

        }
    );

}

// Password change for a signed-in user
//
// The backend requires the current password, so a stolen access token on its
// own is not enough to change it. Nothing here stores or logs a password.

const changePasswordForm =
    document.getElementById("changePasswordForm");


if (changePasswordForm) {

    changePasswordForm.addEventListener(
        "submit",
        async function(event) {

            event.preventDefault();


            const message =
                document.getElementById("changePasswordMessage");

            const currentPassword =
                document.getElementById("currentPassword").value;

            const newPassword =
                document.getElementById("newPassword").value;

            const confirmPassword =
                document.getElementById("confirmPassword").value;

            message.textContent = "";

            if (newPassword !== confirmPassword) {
                message.textContent =
                    "The new passwords do not match.";
                return;
            }

            try {

                const response = await fetch(
                    API_BASE_URL + "/auth/change-password",
                    {
                        method: "POST",
                        headers: authenticatedJsonHeaders(),
                        body: JSON.stringify({
                            current_password: currentPassword,
                            new_password: newPassword
                        })
                    }
                );

                const data =
                    await response.json();

                if (!response.ok) {
                    throw new Error(
                        data.detail || "Could not update the password"
                    );
                }

                changePasswordForm.reset();

                message.style.color = "#166534";
                message.textContent = data.detail;
            } catch (error) {
                console.error(
                    "Change password error:",
                    error
                );

                message.style.color = "#b91c1c";
                message.textContent =
                    error.message || "Could not connect to the backend.";
            }

        }
    );

}

// Applicant account creation
//
// Calls the existing POST /auth/register endpoint, which always assigns the
// applicant role. No token is issued and nothing is stored in localStorage here,
// so the user signs in afterwards through the normal login form.

const signupForm =
    document.getElementById("signupForm");


if (signupForm) {

    signupForm.addEventListener(
        "submit",
        async function(event) {

            event.preventDefault();


            const message =
                document.getElementById("signupMessage");

            const fullName =
                document.getElementById("fullName").value.trim();

            const email =
                document.getElementById("signupEmail").value.trim();

            const password =
                document.getElementById("signupPassword").value;

            const confirmPassword =
                document.getElementById("confirmSignupPassword").value;

            message.textContent = "";

            if (password !== confirmPassword) {
                message.textContent =
                    "The passwords do not match.";
                return;
            }

            try {

                const response = await fetch(
                    API_BASE_URL + "/auth/register",
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            email: email,
                            password: password,
                            full_name: fullName || null
                        })
                    }
                );

                const data =
                    await response.json();

                if (!response.ok) {
                    throw new Error(
                        data.detail || "Could not create the account"
                    );
                }

                message.style.color = "#166534";
                message.textContent =
                    "Account created. Redirecting to login...";

                setTimeout(
                    function() {
                        window.location.href = "login.html";
                    },
                    1200
                );
            } catch (error) {
                console.error(
                    "Sign up error:",
                    error
                );

                message.style.color = "#b91c1c";
                message.textContent =
                    error.message || "Could not connect to the backend.";
            }

        }
    );

}

// Instrument registration

const instrumentForm =
    document.getElementById("instrumentForm");

if (instrumentForm) {

    instrumentForm.addEventListener(
        "submit",
        async function(event) {

            event.preventDefault();

            const instrument = {

                instrument_id:
                    document.getElementById("instrumentId").value,

                instrument_type:
                    document.getElementById("instrumentType").value,

                manufacturer:
                    document.getElementById("manufacturer").value,

                model_number:
                    document.getElementById("model").value,

                serial_number:
                    document.getElementById("serial").value,

                capacity:
                    document.getElementById("capacity").value,

                location:
                    document.getElementById("location").value,

                owner_name:
                    document.getElementById("owner").value

            };

            try {

                const response = await fetch(
                    API_BASE_URL + "/instruments/",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type": "application/json"
                        },

                        body: JSON.stringify(instrument)
                    }
                );

                if (!response.ok) {
                    throw new Error(
                        "Failed to register instrument"
                    );
                }

                const data = await response.json();

                console.log("Instrument registered:", data);

                alert(
                    "Instrument registered successfully!"
                );

                window.location.href =
                    "dashboard.html";

            } catch (error) {

                console.error(error);

                alert(
                    "Could not connect to the backend."
                );
            }

        }
    );

}

// Verification form

const verificationForm =
    document.getElementById("verificationForm");


if (verificationForm) {

    verificationForm.addEventListener(
        "submit",
        async function(event) {

            event.preventDefault();


            const instrumentId =
                document.getElementById("verifyId").value.trim();

            const applicationType =
                document.getElementById("applicationType").value;

            const remarks =
                document.getElementById("remarks").value;


            try {

                // Find the instrument in the backend
                const instrumentsResponse = await fetch(
                    API_BASE_URL + "/instruments/"
                );


                if (!instrumentsResponse.ok) {
                    throw new Error(
                        "Could not load instruments"
                    );
                }


                const instruments =
                    await instrumentsResponse.json();


                const instrument =
                    instruments.find(
                        item =>
                            item.instrument_id === instrumentId
                    );


                if (!instrument) {

                    alert(
                        "Instrument not found. Please enter a registered Instrument ID."
                    );

                    return;

                }


                // Create verification application
                const applicationResponse = await fetch(
                    API_BASE_URL + "/applications/",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type": "application/json"
                        },

                        body: JSON.stringify({

                            instrument_id:
                                instrument.id,

                            application_type:
                                applicationType,

                            status:
                                "Submitted",

                            remarks:
                                remarks

                        })
                    }
                );


                if (!applicationResponse.ok) {

                    throw new Error(
                        "Failed to submit application"
                    );

                }


                const application =
                    await applicationResponse.json();


                console.log(
                    "Application submitted:",
                    application
                );


                // 1. Submit Inspection record to backend
                const standardVal = parseFloat(
                    document.getElementById("standardValue").value
                );
                const measuredVal = parseFloat(
                    document.getElementById("measuredValue").value
                );
                const testResult =
                    document.getElementById("testResult").value;

                const inspectionResponse = await fetch(
                    API_BASE_URL + "/inspections/",
                    {
                        method: "POST",
                        headers: authenticatedJsonHeaders(),
                        body: JSON.stringify({
                            application_id: application.id,
                            standard_value: standardVal,
                            measured_value: measuredVal,
                            result: testResult,
                            inspector_remarks: remarks
                        })
                    }
                );

                let inspection = null;
                if (inspectionResponse.ok) {
                    inspection = await inspectionResponse.json();
                    console.log("Inspection recorded:", inspection);
                }

                // Keep verification test data in localStorage as fallback
                const verification = {
                    applicationId: application.id,
                    applicationNumber: application.application_number,
                    instrumentId: instrumentId,
                    standardValue: standardVal,
                    measuredValue: measuredVal,
                    result: testResult,
                    remarks: remarks,
                    date: new Date().toISOString().split("T")[0]
                };

                localStorage.setItem(
                    "verification",
                    JSON.stringify(verification)
                );

                // 2. If Inspection Passed, issue Certificate from backend
                if (testResult === "Pass" && inspection) {
                    try {
                        const certResponse = await fetch(
                            API_BASE_URL + "/certificates/issue",
                            {
                                method: "POST",
                                headers: authenticatedJsonHeaders(),
                                body: JSON.stringify({
                                    inspection_id: inspection.id,
                                    issuing_authority: "Legal Metrology Department",
                                    remarks: remarks
                                })
                            }
                        );

                        if (certResponse.ok) {
                            const certData = await certResponse.json();
                            alert(
                                "Verification Passed! Official Certificate issued: " +
                                certData.certificate_number
                            );
                            window.location.href =
                                `certificate.html?certificate=${certData.certificate_number}&token=${certData.qr_token}`;
                            return;
                        } else {
                            const errData = await certResponse.json();
                            console.warn("Certificate issue error:", errData);
                        }
                    } catch (certErr) {
                        console.error("Certificate API error:", certErr);
                    }
                } else if (testResult === "Fail") {
                    alert(
                        "Inspection Result: FAIL. Application rejected according to Legal Metrology tolerance limits. No certificate issued."
                    );
                    window.location.href = "dashboard.html";
                    return;
                }

                alert(
                    "Verification application submitted successfully!"
                );

                window.location.href =
                    "certificate.html";

            } catch (error) {

                console.error(error);

                alert(
                    "Could not connect to the backend."
                );

            }

        }
    );

}


// Password visibility toggle
//
// Wraps every password input on the page and injects an eye button that
// switches that input between type="password" and type="text". The value is
// never read, copied, stored or logged: only the type attribute changes.
//
// A real <button type="button"> is used deliberately. It is reachable with
// Tab, activated by Enter or Space, cannot submit the surrounding form, and
// carries aria-label plus aria-pressed so the state is announced. The SVG is
// aria-hidden because the button's own label already describes it.

const PASSWORD_EYE_OPEN =
    '<svg viewBox="0 0 24 24" width="20" height="20" fill="none"' +
    ' stroke="currentColor" stroke-width="2" stroke-linecap="round"' +
    ' stroke-linejoin="round" aria-hidden="true" focusable="false">' +
    '<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"></path>' +
    '<circle cx="12" cy="12" r="3"></circle></svg>';

const PASSWORD_EYE_CLOSED =
    '<svg viewBox="0 0 24 24" width="20" height="20" fill="none"' +
    ' stroke="currentColor" stroke-width="2" stroke-linecap="round"' +
    ' stroke-linejoin="round" aria-hidden="true" focusable="false">' +
    '<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"></path>' +
    '<circle cx="12" cy="12" r="3"></circle>' +
    '<line x1="1" y1="1" x2="23" y2="23"></line></svg>';


// Runs the callback once the document is parsed, whether this file was loaded
// from <head> or from the end of <body>.
function whenDomReady(callback) {

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", callback);
    } else {
        callback();
    }

}


function attachPasswordToggles(root) {

    const inputs =
        (root || document).querySelectorAll('input[type="password"]');

    Array.prototype.forEach.call(inputs, function(input) {

        if (input.getAttribute("data-password-toggle") === "on") {
            return;
        }
        input.setAttribute("data-password-toggle", "on");

        const wrapper = document.createElement("div");
        wrapper.className = "password-field";
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        const button = document.createElement("button");
        button.type = "button";
        button.className = "password-toggle";
        button.innerHTML = PASSWORD_EYE_OPEN;

        if (input.id) {
            button.setAttribute("aria-controls", input.id);
        }

        function apply(visible) {

            input.type = visible ? "text" : "password";

            const label =
                visible ? "Hide password" : "Show password";

            button.innerHTML =
                visible ? PASSWORD_EYE_CLOSED : PASSWORD_EYE_OPEN;

            button.setAttribute("aria-label", label);
            button.setAttribute("aria-pressed", visible ? "true" : "false");
            button.title = label;
        }

        apply(false);

        button.addEventListener(
            "click",
            function() {
                apply(input.type === "password");
            }
        );

        wrapper.appendChild(button);

    });

}


whenDomReady(function() {
    attachPasswordToggles(document);
});

