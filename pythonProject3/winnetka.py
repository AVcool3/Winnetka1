import pandas as pd
import folium
from folium.plugins import MarkerCluster
import requests
import time
from tqdm import tqdm
import os
from datetime import datetime
import signal


class AddressMapper:
    def __init__(self, api_key):
        self.api_key = api_key
        self.interrupted = False
        signal.signal(signal.SIGINT, self.handle_interrupt)

    def handle_interrupt(self):
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

    def create_map(self, geocoded_data, labels):
        if not geocoded_data:
            raise ValueError("No geocoded data provided")

        winnetka_center = [42.1080, -87.7352]

        m = folium.Map(
            location=winnetka_center,
            zoom_start=14,
            tiles='OpenStreetMap'
        )

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
            print("Creating map...")
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
