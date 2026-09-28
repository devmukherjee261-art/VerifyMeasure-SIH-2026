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

