Project Goals:

HA App deployed via Github.
Serves requested data via http on a basic webpage.
The app will have access to the CTA Train Tracker API. The API key is set via a app option.
Documentation for the API is available here.

The app should routinely poll the Locations API and/or Follow This Train API and store the collected data.
https://www.transitchicago.com/developers/ttdocs/

Actual Data that needs to be gathered from what is collected from the API:
 - When a train on the blue line that is forest park bound (trDr is 5) departs Harlem station (stop_id is 40980), what is the stop_id of the stop the train shows up at next?
 - When a train on the red line that is Howard bound (trDr is 1) departs Morse station (stop_id is 40100), what is the stop_id of the stop the train shows up at next?