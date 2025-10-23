import os
import subprocess
import sys
import csv
from datetime import datetime
import logging
from django.shortcuts import render, redirect
from django.http import FileResponse, HttpResponse
from django.conf import settings
from django.db.models import Avg, Max
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
import openpyxl
from .models import SpeedViolation, Video

def home(request):
    return render(request, 'home.html')

def contact(request):
    return render(request, 'contact.html')

def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

@login_required
def dashboard(request):
    videos = Video.objects.filter(user=request.user).order_by('-uploaded_at')
    return render(request, 'detection/dashboard.html', {'videos': videos})

def process_csv(csv_path, video):
    SpeedViolation.objects.filter(video=video).delete()
    if not os.path.exists(csv_path):
        logging.warning(f"CSV file not found: {csv_path}")
        return
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            SpeedViolation.objects.create(
                video=video,
                frame_id=int(row.get('TrackID', 0)),
                timestamp=datetime.strptime(row['Timestamp'], '%Y-%m-%d %H:%M:%S'),
                vehicle=row['Vehicle'],
                speed=float(row['Speed (km/h)']),
                plate=row['License Plate'],
                location=row['Location']
            )

@login_required
def upload_video(request):
    if request.method == 'POST' and request.FILES.get('video'):
        video_file = request.FILES['video']
        title = request.POST.get('title', video_file.name)
        video = Video.objects.create(
            user=request.user,
            title=title,
            file=video_file
        )
        processed_dir = os.path.join(settings.MEDIA_ROOT, 'processed')
        os.makedirs(processed_dir, exist_ok=True)
        processed_output_path = os.path.join(processed_dir, os.path.basename(video_file.name))

        try:
            result = subprocess.run([
                sys.executable, 'final_system.py', video.file.path, processed_output_path
            ], capture_output=True, text=True, timeout=600, encoding='utf-8')

            logging.info(f"Processing stdout: {result.stdout}")
            logging.error(f"Processing stderr: {result.stderr}")

            if os.path.exists(processed_output_path):
                rel_processed = os.path.relpath(processed_output_path, settings.MEDIA_ROOT)
                video.result_file.name = rel_processed
                video.processed = True
                video.save()
                logging.info(f"Processed video saved and linked: {rel_processed}")
            else:
                logging.error("Processed video was NOT created")

            csv_path = os.path.join(os.getcwd(), 'speed_violations.csv')
            process_csv(csv_path, video)

        except Exception as e:
            logging.error(f"Processing error: {e}")

        return redirect('dashboard')

    return render(request, 'detection/upload.html')

@login_required
def view_results(request, video_id):
    video = Video.objects.filter(id=video_id, user=request.user).first()
    if not video:
        return HttpResponse("Not found or unauthorized", status=404)

    violations = video.violations.all().order_by('-timestamp')

    unique_trackids = set(viol.frame_id for viol in violations)
    overspeed_ids = {viol.frame_id for viol in violations if viol.speed > 80}
    total_vehicles = len(unique_trackids)
    overspeed_count = len(overspeed_ids)
    normal_count = max(0, total_vehicles - overspeed_count)
    avg_speed = violations.aggregate(avg=Avg('speed'))['avg'] or 0
    top_speed = violations.aggregate(max=Max('speed'))['max'] or 0

    return render(request, 'detection/results.html', {
        'violations': violations[:50],
        'total_vehicles': total_vehicles,
        'overspeed_count': overspeed_count,
        'normal_count': normal_count,
        'avg_speed': round(avg_speed, 2),
        'top_speed': round(top_speed, 2),
        'video': video,
    })

@login_required
def download_video(request, video_id):
    video = Video.objects.filter(id=video_id, user=request.user).first()
    if not video or not video.result_file:
        return HttpResponse("Processed video not found.", status=404)

    file_path = video.result_file.path
    if not os.path.exists(file_path):
        return HttpResponse("Processed video file missing.", status=404)

    return FileResponse(open(file_path, 'rb'), content_type='video/mp4')

@login_required
def delete_video(request, video_id):
    video = Video.objects.filter(id=video_id, user=request.user).first()
    if video:
        video.delete()
    return redirect('dashboard')

@login_required
def download_csv(request):
    last_video = Video.objects.filter(user=request.user).order_by('-uploaded_at').first()
    if not last_video:
        return HttpResponse("No video uploaded yet.", status=404)
    csv_path = os.path.join(os.getcwd(), 'speed_violations.csv')
    if not os.path.exists(csv_path):
        return HttpResponse("No CSV generated yet.", status=404)
    return FileResponse(open(csv_path, 'rb'), as_attachment=True, filename='speed_violations.csv')

@login_required
def download_excel(request):
    last_video = Video.objects.filter(user=request.user).order_by('-uploaded_at').first()
    if not last_video:
        return HttpResponse("No video uploaded yet.", status=404)
    violations = last_video.violations.all().order_by('-timestamp')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Violations"
    ws.append(["TrackID", "Time", "Vehicle", "Speed (km/h)", "Plate", "Location"])
    for v in violations:
        ws.append([
            v.frame_id,
            v.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            v.vehicle,
            v.speed,
            v.plate,
            v.location
        ])
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = 'attachment; filename=violations.xlsx'
    wb.save(response)
    return response
