import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import pydeck as pdk
import altair as alt
from streamlit_folium import folium_static
import folium
import numpy as np

# Page configuration
st.set_page_config(
    page_title="LinkedIn Digital Footprint Analyzer",
    page_icon="🕵️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better appearance
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        background: linear-gradient(90deg, #0072b1, #00a0dc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        padding: 0.5rem 0;
    }
    .metric-card {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .section-header {
        background-color: #0077b5;
        color: white;
        padding: 0.5rem;
        border-radius: 5px;
        margin-bottom: 1rem;
    }
    .caption {
        font-size: 0.8rem;
        color: #666;
    }
</style>
""", unsafe_allow_html=True)


# Load log files
@st.cache_data
def load_data():
    try:
        with open("linkedin_enhanced_footprints.json") as f:
            formatted = json.load(f)
        with open("linkedin_raw_logs.json") as f:
            raw = json.load(f)
        return formatted, raw
    except FileNotFoundError:
        st.error("⚠️ Log files not found. Make sure to run the LinkedIn Enhanced Logger first.")
        st.info("Run: `python linkedin_enhanced_logger.py` to collect data before using this dashboard.")
        return [], {"formatted": [], "raw": []}


def get_timestamp_df(data, type_filter=None):
    """Extract timestamps and convert to DataFrame for timeline visualizations"""
    filtered = data if not type_filter else [d for d in data if d.get("type") == type_filter]
    times = [datetime.fromisoformat(d.get("timestamp", "").replace('Z', '+00:00')) for d in filtered]
    types = [d.get("type", "unknown") for d in filtered]
    return pd.DataFrame({"timestamp": times, "type": types})


def sidebar_filters(formatted_data):
    """Create sidebar filters for data visualization"""
    st.sidebar.header("🔍 Filter Data")

    # Get unique event types
    event_types = list(set([d.get("type") for d in formatted_data if "type" in d]))
    selected_types = st.sidebar.multiselect(
        "Event Types",
        options=event_types,
        default=event_types if event_types else None
    )

    # Time range filter
    if formatted_data:
        all_timestamps = [datetime.fromisoformat(d.get("timestamp", "").replace('Z', '+00:00'))
                          for d in formatted_data if "timestamp" in d]
        if all_timestamps:
            min_time, max_time = min(all_timestamps), max(all_timestamps)
            selected_time_range = st.sidebar.slider(
                "Time Range",
                min_value=min_time,
                max_value=max_time,
                value=(min_time, max_time)
            )
        else:
            selected_time_range = None
    else:
        selected_time_range = None

    return selected_types, selected_time_range


def filtered_data(formatted_data, selected_types=None, selected_time_range=None):
    """Filter data based on sidebar selections"""
    filtered = formatted_data

    if selected_types:
        filtered = [d for d in filtered if d.get("type") in selected_types]

    if selected_time_range:
        start_time, end_time = selected_time_range
        filtered = [d for d in filtered if
                    start_time <= datetime.fromisoformat(d.get("timestamp", "").replace('Z', '+00:00')) <= end_time]

    return filtered


# Dashboard components
def show_header():
    """Display dashboard header with title and description"""
    st.markdown("<h1 class='main-header'>🕵️‍♀️ LinkedIn Digital Footprint Analyzer</h1>", unsafe_allow_html=True)
    st.markdown("""
    This dashboard analyzes your LinkedIn browsing session to reveal what digital footprints you leave behind.
    See device info, location data, network activity, permissions, and resource usage.
    """)


def show_location_map(data):
    """Display location information on a map"""
    location_data = [d for d in data if d.get("type") == "location_info"]

    if not location_data:
        st.warning("No location data available")
        return

    location = location_data[-1].get("details", {})

    st.markdown("<h3 class='section-header'>📍 Your Location</h3>", unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        # Create map if coordinates are available
        if "loc" in location and location["loc"]:
            try:
                lat, lon = map(float, location["loc"].split(","))
                m = folium.Map(location=[lat, lon], zoom_start=10)
                folium.Marker(
                    [lat, lon],
                    popup=f"IP: {location.get('ip', 'Unknown')}",
                    tooltip="Your Location"
                ).add_to(m)
                folium_static(m)
            except:
                st.error("Could not display map with provided coordinates")
        else:
            st.info("No precise coordinates available for mapping")

    with col2:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.metric("📱 IP Address", location.get("ip", "Unknown"))
        st.metric("🏙️ City/Region", f"{location.get('city', 'Unknown')}, {location.get('region', 'Unknown')}")
        st.metric("🌎 Country", location.get("country", "Unknown"))
        st.metric("🏢 ISP/Organization", location.get("org", "Unknown"))
        st.markdown("</div>", unsafe_allow_html=True)

        st.caption("This is the location data websites can see when you visit them")


def show_device_info(data):
    """Display device hardware and software information"""
    device_data = [d for d in data if d.get("type") == "device_info"]

    if not device_data:
        st.warning("No device information available")
        return

    device = device_data[-1].get("details", {})

    st.markdown("<h3 class='section-header'>💻 Device Information</h3>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.subheader("🖥️ System")
        st.metric("Operating System", f"{device.get('os', 'Unknown')} {device.get('os_version', '')}")
        st.metric("Architecture", device.get("architecture", "Unknown"))
        st.metric("Hostname", device.get("hostname", "Unknown"))
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.subheader("🧠 Hardware")
        st.metric("CPU", device.get("processor", "Unknown"))
        st.metric("CPU Cores",
                  f"{device.get('physical_cpu_cores', 'Unknown')} physical / {device.get('cpu_cores', 'Unknown')} logical")
        st.metric("RAM", device.get("total_ram", "Unknown"))
        st.markdown("</div>", unsafe_allow_html=True)

    with col3:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.subheader("💾 Storage & Network")
        st.metric("Disk Space", device.get("disk_total", "Unknown"))
        st.metric("Free Space", device.get("disk_free", "Unknown"))
        st.metric("Local IP", device.get("local_ip", "Unknown"))
        st.markdown("</div>", unsafe_allow_html=True)

    # Resource usage visualization
    resource_data = [d for d in data if d.get("type") == "system_resources"]

    if resource_data:
        st.subheader("System Resource Usage During Session")

        # Prepare data for charts
        times = [datetime.fromisoformat(d.get("timestamp", "").replace('Z', '+00:00')) for d in resource_data]
        cpu_values = [d.get("cpu_percent", 0) for d in resource_data]
        memory_values = [d.get("memory_percent", 0) for d in resource_data]

        # Create dataframe
        df_resources = pd.DataFrame({
            "Time": times,
            "CPU (%)": cpu_values,
            "Memory (%)": memory_values
        })

        # Plot with Plotly
        fig = px.line(df_resources, x="Time", y=["CPU (%)", "Memory (%)"],
                      labels={"value": "Usage %", "variable": "Resource Type"},
                      title="Resource Usage Over Time")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)


def show_permissions(data):
    """Display permissions granted to LinkedIn"""
    permissions_data = [d for d in data if d.get("type") == "permissions_status"]

    if not permissions_data:
        st.warning("No permissions data available")
        return

    permissions = permissions_data[-1].get("statuses", {})

    st.markdown("<h3 class='section-header'>🔐 Permissions</h3>", unsafe_allow_html=True)

    # Create dataframe for permission status
    permission_items = list(permissions.items())
    permission_names = [item[0] for item in permission_items]
    permission_statuses = [item[1] for item in permission_items]

    # Convert status to numeric for coloring
    status_colors = []
    for status in permission_statuses:
        if status == "granted":
            status_colors.append("green")
        elif status == "prompt":
            status_colors.append("orange")
        elif status == "denied":
            status_colors.append("red")
        else:
            status_colors.append("gray")

    # Plot horizontal bar chart with status colors
    fig = go.Figure()

    for i, (name, status, color) in enumerate(zip(permission_names, permission_statuses, status_colors)):
        fig.add_trace(go.Bar(
            y=[name],
            x=[1],
            orientation='h',
            name=status,
            marker_color=color,
            text=status,
            textposition='inside',
            insidetextanchor='middle',
            hoverinfo='text',
            hovertext=f"{name}: {status}"
        ))

    fig.update_layout(
        title="Website Permissions Status",
        height=400,
        barmode='stack',
        showlegend=False,
        xaxis=dict(
            showticklabels=False,
            showgrid=False,
            zeroline=False
        )
    )

    st.plotly_chart(fig, use_container_width=True)

    # Show media devices
    media_data = [d for d in data if d.get("type") == "media_devices"]
    if media_data:
        devices = media_data[-1].get("devices", [])
        if isinstance(devices, list) and devices:
            st.subheader("📷 Media Devices That Can Be Accessed")

            # Create columns for different device types
            webcams = [d for d in devices if d.get("kind") == "videoinput"]
            mics = [d for d in devices if d.get("kind") == "audioinput"]
            speakers = [d for d in devices if d.get("kind") == "audiooutput"]

            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown(f"**Cameras ({len(webcams)})**")
                for cam in webcams:
                    st.markdown(f"• {cam.get('label', 'Unnamed camera')}")

            with col2:
                st.markdown(f"**Microphones ({len(mics)})**")
                for mic in mics:
                    st.markdown(f"• {mic.get('label', 'Unnamed microphone')}")

            with col3:
                st.markdown(f"**Speakers ({len(speakers)})**")
                for speaker in speakers:
                    st.markdown(f"• {speaker.get('label', 'Unnamed speaker')}")


def show_network_activity(data, raw_data):
    """Display network activity visualization"""
    st.markdown("<h3 class='section-header'>🌐 Network Activity</h3>", unsafe_allow_html=True)

    # Get request/response data
    requests = [r for r in raw_data.get("raw", []) if r.get("type") == "request"]
    responses = [r for r in raw_data.get("raw", []) if r.get("type") == "response"]

    if not requests and not responses:
        st.warning("No network activity recorded")
        return

    col1, col2 = st.columns(2)

    with col1:
        # Request methods visualization
        if requests:
            methods = [r.get("method", "Unknown") for r in requests]
            method_counts = pd.Series(methods).value_counts().reset_index()
            method_counts.columns = ["Method", "Count"]

            fig = px.pie(method_counts, values="Count", names="Method",
                         title=f"Request Methods (Total: {len(requests)})",
                         color_discrete_sequence=px.colors.qualitative.Set3)
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Response codes visualization
        if responses:
            status_codes = [r.get("status", 0) for r in responses]
            # Group status codes by class (2xx, 3xx, 4xx, 5xx)
            status_classes = []
            for code in status_codes:
                if 200 <= code < 300:
                    status_classes.append("2xx (Success)")
                elif 300 <= code < 400:
                    status_classes.append("3xx (Redirect)")
                elif 400 <= code < 500:
                    status_classes.append("4xx (Client Error)")
                elif 500 <= code < 600:
                    status_classes.append("5xx (Server Error)")
                else:
                    status_classes.append("Other")

            status_counts = pd.Series(status_classes).value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]

            # Color mapping for status codes
            color_map = {
                "2xx (Success)": "green",
                "3xx (Redirect)": "blue",
                "4xx (Client Error)": "orange",
                "5xx (Server Error)": "red",
                "Other": "gray"
            }

            fig = px.pie(status_counts, values="Count", names="Status",
                         title=f"Response Status Codes (Total: {len(responses)})",
                         color="Status", color_discrete_map=color_map)
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)

    # Request timeline
    if requests:
        st.subheader("Network Request Timeline")

        # Convert timestamps to datetime
        request_times = [datetime.fromisoformat(r.get("timestamp", "").replace('Z', '+00:00'))
                         for r in requests]

        # Extract domains for categorization
        def extract_domain(url):
            try:
                from urllib.parse import urlparse
                return urlparse(url).netloc
            except:
                return "unknown"

        domains = [extract_domain(r.get("url", "")) for r in requests]

        # Create dataframe
        df_requests = pd.DataFrame({
            "Time": request_times,
            "Domain": domains,
            "Method": [r.get("method", "Unknown") for r in requests],
            "URL": [r.get("url", "Unknown") for r in requests]
        })

        # Plot timeline with Altair
        chart = alt.Chart(df_requests).mark_circle(size=60).encode(
            x=alt.X('Time:T', title='Time'),
            y=alt.Y('Domain:N', title='Domain', sort='-x'),
            color=alt.Color('Method:N', scale=alt.Scale(scheme='category10')),
            tooltip=['Time', 'Domain', 'Method', 'URL']
        ).properties(
            height=400
        ).interactive()

        st.altair_chart(chart, use_container_width=True)

        # Allow expanding to see full network logs
        with st.expander("View Detailed Network Logs"):
            tab1, tab2 = st.tabs(["Requests", "Responses"])

            with tab1:
                req_df = pd.DataFrame([{
                    "Time": datetime.fromisoformat(r.get("timestamp", "").replace('Z', '+00:00')),
                    "Method": r.get("method", ""),
                    "URL": r.get("url", ""),
                    "Headers": str(r.get("headers", {}))[:100] + "..." if r.get("headers") else ""
                } for r in requests])

                st.dataframe(req_df, use_container_width=True)

            with tab2:
                res_df = pd.DataFrame([{
                    "Time": datetime.fromisoformat(r.get("timestamp", "").replace('Z', '+00:00')),
                    "Status": r.get("status", ""),
                    "URL": r.get("url", ""),
                    "Headers": str(r.get("headers", {}))[:100] + "..." if r.get("headers") else ""
                } for r in responses])

                st.dataframe(res_df, use_container_width=True)


def show_browser_data(data):
    """Display browser storage and caching information"""
    st.markdown("<h3 class='section-header'>🗄️ Browser Storage & Caching</h3>", unsafe_allow_html=True)

    cache_data = [d for d in data if d.get("type") == "cache_data"]
    service_workers = [d for d in data if d.get("type") == "service_workers"]

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🤖 Service Workers")
        if service_workers and service_workers[-1].get("registered_scopes"):
            scopes = service_workers[-1].get("registered_scopes", [])
            st.info(f"LinkedIn has {len(scopes)} active service worker(s)")
            for scope in scopes:
                st.markdown(f"• `{scope}`")
        else:
            st.info("No service workers detected")

        st.caption("Service workers allow websites to work offline and send push notifications")

    with col2:
        st.subheader("💾 Cache Storage")
        if cache_data and cache_data[-1].get("cached_urls"):
            cached_urls = cache_data[-1].get("cached_urls", [])
            st.info(f"LinkedIn has {len(cached_urls)} cached resource(s)")

            # Extract domains from cached URLs
            domains = {}
            for url in cached_urls:
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                    domains[domain] = domains.get(domain, 0) + 1
                except:
                    pass

            # Display domain distribution
            if domains:
                domain_df = pd.DataFrame({
                    "Domain": list(domains.keys()),
                    "Count": list(domains.values())
                }).sort_values("Count", ascending=False)

                fig = px.bar(domain_df.head(10), x="Count", y="Domain",
                             orientation='h', title="Top Domains in Cache")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No cached data detected")

        st.caption("Browser caching stores website data for faster loading")


def show_user_activity(data):
    """Display user interaction patterns"""
    st.markdown("<h3 class='section-header'>👤 User Interaction Analysis</h3>", unsafe_allow_html=True)

    # Filter activity data
    clicks = [d for d in data if d.get("event") == "click"]
    scrolls = [d for d in data if d.get("event") == "scroll"]
    keyboard = [d for d in data if d.get("event") == "keyboard_input"]
    visibility = [d for d in data if d.get("event") == "tab_visibility"]

    col1, col2 = st.columns(2)

    with col1:
        # Mouse click heatmap
        st.subheader("🖱️ Click Distribution")
        if clicks:
            # Create dataframe with click coordinates
            click_df = pd.DataFrame({
                "x": [c.get("x", 0) for c in clicks],
                "y": [c.get("y", 0) for c in clicks],
                "element": [c.get("tag", "Unknown") for c in clicks]
            })

            # Create scatter plot of clicks
            fig = px.scatter(click_df, x="x", y="y", color="element",
                             title=f"Mouse Click Distribution ({len(clicks)} clicks)",
                             labels={"x": "X Coordinate", "y": "Y Coordinate"},
                             hover_data=["element"])

            # Invert y-axis to match screen coordinates
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No click data recorded")

    with col2:
        # Scroll depth visualization
        st.subheader("📜 Scroll Depth Analysis")
        if scrolls:
            # Create dataframe with scroll positions
            scroll_df = pd.DataFrame({
                "Time": [datetime.fromisoformat(s.get("timestamp", "").replace('Z', '+00:00')) for s in scrolls],
                "Depth (%)": [s.get("scrollPercentage", 0) for s in scrolls]
            })

            # Create line chart of scroll depth
            fig = px.line(scroll_df, x="Time", y="Depth (%)",
                          title=f"Scroll Depth Over Time ({len(scrolls)} events)",
                          labels={"Depth (%)": "Page Scroll Depth %"})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No scroll data recorded")

    # Create user activity timeline
    st.subheader("⏱️ User Activity Timeline")

    # Combine all user activities with timestamps
    all_activities = []

    # Add clicks
    for c in clicks:
        all_activities.append({
            "Time": datetime.fromisoformat(c.get("timestamp", "").replace('Z', '+00:00')),
            "Activity": "Click",
            "Detail": f"Clicked on {c.get('tag', 'element')}: {c.get('text', '')[:30]}"
        })

    # Add scrolls
    for s in scrolls:
        all_activities.append({
            "Time": datetime.fromisoformat(s.get("timestamp", "").replace('Z', '+00:00')),
            "Activity": "Scroll",
            "Detail": f"Scrolled to {s.get('scrollPercentage', 0)}% of page"
        })

    # Add keyboard inputs
    for k in keyboard:
        all_activities.append({
            "Time": datetime.fromisoformat(k.get("timestamp", "").replace('Z', '+00:00')),
            "Activity": "Keyboard",
            "Detail": f"Typed in {k.get('target', 'unknown')} element"
        })

    # Add tab visibility changes
    for v in visibility:
        all_activities.append({
            "Time": datetime.fromisoformat(v.get("timestamp", "").replace('Z', '+00:00')),
            "Activity": "Tab Focus",
            "Detail": f"Tab became {v.get('state', 'unknown')}"
        })

    if all_activities:
        # Convert to dataframe and sort by time
        activity_df = pd.DataFrame(all_activities).sort_values("Time")

        # Create timeline chart
        chart = alt.Chart(activity_df).mark_circle(size=100).encode(
            x=alt.X('Time:T', title='Time'),
            y=alt.Y('Activity:N', title='Activity Type'),
            color='Activity:N',
            tooltip=['Time', 'Activity', 'Detail']
        ).properties(
            height=300
        ).interactive()

        st.altair_chart(chart, use_container_width=True)

        # Show activity table in expander
        with st.expander("View Detailed User Activity Log"):
            st.dataframe(activity_df, use_container_width=True)
    else:
        st.info("No user activity data recorded")


def show_session_summary(data):
    """Display overall session summary and statistics"""
    session_data = [d for d in data if d.get("type") == "session_summary"]

    if not session_data:
        return

    session = session_data[-1]

    st.markdown("<h3 class='section-header'>📊 Session Summary</h3>", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        duration = session.get("session_duration_seconds", 0)
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        st.metric("⏱️ Session Duration", f"{minutes}m {seconds}s")

    with col2:
        requests_count = session.get("requests_count", 0)
        st.metric("📤 Requests Sent", requests_count)

    with col3:
        responses_count = session.get("responses_count", 0)
        st.metric("📥 Responses Received", responses_count)

    with col4:
        clicks_count = len([d for d in data if d.get("event") == "click"])
        st.metric("🖱️ User Clicks", clicks_count)

    # Data collection timeline
    event_df = get_timestamp_df(data)
    if not event_df.empty:
        st.subheader("Data Collection Timeline")

        # Count events by type and time
        event_df['minute'] = event_df['timestamp'].dt.floor('Min')
        timeline = event_df.groupby(['minute', 'type']).size().reset_index(name='count')

        # Plot timeline
        fig = px.bar(timeline, x="minute", y="count", color="type",
                     title="Events Collected Over Time",
                     labels={"minute": "Time", "count": "Number of Events", "type": "Event Type"})
        st.plotly_chart(fig, use_container_width=True)


def main():
    show_header()

    # Load data
    formatted, raw_data = load_data()

    if not formatted:
        return

    # Apply filters from sidebar
    selected_types, selected_time_range = sidebar_filters(formatted)
    filtered_formatted = filtered_data(formatted, selected_types, selected_time_range)

    # Add refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.experimental_rerun()

    # Show session summary at the top
    show_session_summary(filtered_formatted)

    # Create tabs for different categories of information
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📱 Device & Location",
        "🔐 Permissions & Resources",
        "🌐 Network Activity",
        "👤 User Behavior",
        "🧪 Raw Data Explorer"
    ])

    with tab1:
        show_location_map(filtered_formatted)
        show_device_info(filtered_formatted)

    with tab2:
        show_permissions(filtered_formatted)
        show_browser_data(filtered_formatted)

    with tab3:
        show_network_activity(filtered_formatted, raw_data)

    with tab4:
        show_user_activity(filtered_formatted)

    with tab5:
        st.subheader("🧾 Raw Data Explorer")
        st.json(raw_data)

    # Footer
    st.markdown("---")
    st.caption("This dashboard analyzes your digital footprint on LinkedIn. Data is collected locally and not shared.")
    st.caption("Built with Streamlit, Plotly, and Altair for data visualization.")


if __name__ == "__main__":
    main()