from tqdm import tqdm
import os
from datetime import datetime
import signal
import time
import requests
import pandas as pd
import folium
from folium.plugins import MarkerCluster


class AddressMapper:
    def __init__(self, api_key):
        self.api_key = api_key
        self.interrupted = False
        signal.signal(signal.SIGINT, self.handle_interrupt)

    def handle_interrupt(self, signum, frame):
        print("\nGracefully shutting down...")
        self.interrupted = True

    def geocode_address(self, full_address):
        if self.interrupted:
            return None

        url = "https://us1.locationiq.com/v1/search.php"
        params = {
            'key': self.api_key,
            'q': full_address,
            'format': 'json'
        }
        try:
            time.sleep(1)
            response = requests.get(url, params=params)

            if response.status_code == 401:
                print("\nError: Invalid API key. Please check your LocationIQ API key.")
                self.interrupted = True
                return None

            response.raise_for_status()
            data = response.json()
            return {
                'address': full_address,
                'lat': float(data[0]['lat']),
                'lon': float(data[0]['lon'])
            }
        except requests.exceptions.RequestException as e:
            print(f"\nError geocoding {full_address}: {str(e)}")
            if "Too Many Requests" in str(e):
                print("Rate limit exceeded. Increasing delay...")
                time.sleep(5)
            return None
        except Exception as e:
            print(f"\nError geocoding {full_address}: {str(e)}")
            return None

    def batch_geocode(self, addresses):
        results = []
        print(f"Geocoding {len(addresses)} addresses...")

        with tqdm(total=len(addresses), ncols=70) as pbar:
            for address in addresses:
                if self.interrupted:
                    break

                result = self.geocode_address(address)
                if result:
                    results.append(result)
                pbar.update(1)

        return results

    def add_polygon(self, m, coordinates, color='red', fill_color='red',
                    fill_opacity=0.2, popup_text=None):
        """
        Add a polygon to the map using coordinates with a centered label.
        """
        # Add the polygon
        folium.Polygon(
            locations=coordinates,
            color=color,
            fill_color=fill_color,
            fill_opacity=fill_opacity,
            popup=folium.Popup(popup_text, max_width=300) if popup_text else None
        ).add_to(m)

        # Calculate centroid of polygon for better label placement
        def calculate_centroid(coords):
            area = 0
            cx = 0
            cy = 0
            for i in range(len(coords) - 1):
                lat1, lon1 = coords[i]
                lat2, lon2 = coords[i + 1]
                cross = lat1 * lon2 - lat2 * lon1
                area += cross
                cx += (lat1 + lat2) * cross
                cy += (lon1 + lon2) * cross
            area /= 2
            cx = cx / (6 * area)
            cy = cy / (6 * area)
            return abs(cx), abs(cy)

        # Get centroid
        center_lat, center_lon = calculate_centroid(coordinates)

        # Add label at centroid
        if popup_text:
            label_html = f'''
                <div style="
                    color: {color};
                    font-weight: bold;
                    font-size: 16px;
                    text-align: center;
                    text-shadow: 2px 2px 2px white, -2px -2px 2px white, 2px -2px 2px white, -2px 2px 2px white;
                ">{popup_text}</div>
            '''

            folium.DivIcon(
                html=label_html,
            ).add_to(folium.Marker(
                [center_lat, center_lon],
                icon=folium.DivIcon(html=label_html)
            ).add_to(m))

    def create_map(self, geocoded_data, labels, polygons=None):
        """
        Create a map with markers and optional polygons.

        Args:
            geocoded_data: List of dicts with geocoded addresses
            labels: List of labels for the markers
            polygons: List of dicts with polygon information, each containing:
                     - coordinates: List of [lat, lon] pairs
                     - color: (optional) Stroke color
                     - fill_color: (optional) Fill color
                     - fill_opacity: (optional) Fill opacity
                     - popup_text: (optional) Popup text
        """
        if not geocoded_data:
            raise ValueError("No geocoded data provided")

        winnetka_center = [42.1080, -87.7352]

        m = folium.Map(
            location=winnetka_center,
            zoom_start=14,
            tiles='OpenStreetMap'
        )

        # Add polygons first (if provided) so they appear under the markers
        if polygons:
            for polygon in polygons:
                self.add_polygon(
                    m,
                    coordinates=polygon['coordinates'],
                    color=polygon.get('color', 'red'),
                    fill_color=polygon.get('fill_color', 'red'),
                    fill_opacity=polygon.get('fill_opacity', 0.2),
                    popup_text=polygon.get('popup_text')
                )

        # Add markers with clustering
        marker_cluster = MarkerCluster().add_to(m)

        for i, point in enumerate(geocoded_data):
            label = labels[i]
            popup_text = f"""
            <div style="min-width: 200px;">
                <h4 style="margin-bottom: 10px;">{label}</h4>
                <p><strong>Address:</strong><br>{point['address']}</p>
            </div>
            """

            folium.Marker(
                [point['lat'], point['lon']],
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=label
            ).add_to(marker_cluster)

        return m


def main():
    try:
        from config import API_KEY
    except ImportError:
        print("Error: Please create a config.py file with your API_KEY")
        return
    except Exception as e:
        print(f"Error loading API key: {str(e)}")
        return

    INPUT_FILE = 'addresses.csv'

    if not API_KEY or API_KEY == '':
        print("Error: Please set your actual API key in config.py")
        return

    os.makedirs('output', exist_ok=True)
    mapper = AddressMapper(API_KEY)

    try:
        print("Reading addresses from CSV...")
        df = pd.read_csv(INPUT_FILE)

        df = df[
            (df['city'].str.lower() == 'winnetka') &
            (df['state'].str.lower() == 'il')
            ]

        full_addresses = df.apply(
            lambda row: f"{row['address']}, {row['city']}, {row['state']}",
            axis=1
        ).tolist()

        labels = df['label'].tolist()

        print("Geocoding addresses...")
        geocoded_data = mapper.batch_geocode(full_addresses)

        if geocoded_data:
            print("Loading polygon coordinates from CSV...")
            try:
                # Define colors for the polygons
                colors = [
                    'blue', 'red', 'green', 'purple',
                    'orange', 'darkblue', 'darkred', 'darkgreen',
                    'cadetblue', 'darkpurple', 'pink', 'lightblue',
                    'lightred', 'lightgreen', 'gray', 'black'
                ]

                # Read the polygon definitions
                polygon_df = pd.read_csv('polygons.csv')
                polygons = []

                # Group by polygon_id to handle multiple vertices per polygon
                for polygon_id, group in polygon_df.groupby('polygon_id'):
                    # Sort by vertex_order if it exists
                    if 'vertex_order' in group.columns:
                        group = group.sort_values('vertex_order')

                    # Extract coordinates
                    coordinates = group[['lat', 'lon']].values.tolist()

                    # Close the polygon by adding the first point at the end if needed
                    if coordinates[0] != coordinates[-1]:
                        coordinates.append(coordinates[0])

                    polygons.append({
                        'coordinates': coordinates,
                        'color': colors[len(polygons) % len(colors)],
                        'fill_color': colors[len(polygons) % len(colors)],
                        'fill_opacity': 0.2,
                        'popup_text': group['name'].iloc[0] if 'name' in group else f'Area {polygon_id}'
                    })

                print("Creating map...")
                map_obj = mapper.create_map(
                    geocoded_data,
                    labels,
                    polygons=polygons
                )

                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_file = f'output/winnetka_map_{timestamp}.html'
                map_obj.save(output_file)
                print(f"Map saved to {output_file}")
            except FileNotFoundError:
                print("Note: polygons.csv not found. Creating map without polygons...")
                map_obj = mapper.create_map(geocoded_data, labels)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_file = f'output/winnetka_map_{timestamp}.html'
                map_obj.save(output_file)
                print(f"Map saved to {output_file}")
        else:
            print("No addresses were successfully geocoded.")

    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()