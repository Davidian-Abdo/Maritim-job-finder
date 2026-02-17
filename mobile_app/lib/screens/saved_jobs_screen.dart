import 'package:flutter/material.dart';
import 'package:flutter/services.dart'; // for Clipboard
import 'package:provider/provider.dart';
import 'package:pull_to_refresh/pull_to_refresh.dart';
import 'package:url_launcher/url_launcher.dart';
import '../api_client.dart';

class SavedJobsScreen extends StatefulWidget {
  const SavedJobsScreen({super.key});

  @override
  State<SavedJobsScreen> createState() => _SavedJobsScreenState();
}

class _SavedJobsScreenState extends State<SavedJobsScreen> {
  final RefreshController _refreshController = RefreshController();
  List<Job> _savedJobs = [];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _fetchSavedJobs();
  }

  Future<void> _fetchSavedJobs() async {
    setState(() => _isLoading = true);
    try {
      final api = context.read<ApiClient>();
      final jobs = await api.getSavedJobs();
      setState(() => _savedJobs = jobs);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${e.toString()}')),
        );
      }
    } finally {
      setState(() => _isLoading = false);
      _refreshController.refreshCompleted();
    }
  }

  Future<void> _unsaveJob(int jobId) async {
    try {
      await context.read<ApiClient>().unsaveJob(jobId);
      await _fetchSavedJobs(); // refresh list
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Job removed')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${e.toString()}')),
        );
      }
    }
  }

  // ==================== URL HANDLING (same as JobsScreen) ====================
  Future<void> _openJobUrl(String urlString) async {
    final Uri? uri = Uri.tryParse(urlString);
    if (uri == null || !uri.hasScheme) {
      _showUrlErrorDialog('The link is malformed or missing.');
      return;
    }

    final canLaunch = await canLaunchUrl(uri);
    if (!canLaunch) {
      _showNoBrowserDialog(uri.toString());
      return;
    }

    try {
      final launched = await launchUrl(
        uri,
        mode: LaunchMode.externalApplication,
      );
      if (!launched) {
        _showUrlErrorDialog('Could not open the link. You can try copying it.');
      }
    } catch (e) {
      debugPrint('Error launching URL: $e');
      _showUrlErrorDialog('An unexpected error occurred while opening the link.');
    }
  }

  void _showNoBrowserDialog(String url) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('No browser found'),
        content: Text(
          'Your device does not have a browser that can open this link.\n\n'
          'You can copy the link and open it manually.'
        ),
        actions: [
          TextButton(
            onPressed: () {
              Clipboard.setData(ClipboardData(text: url));
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Link copied to clipboard')),
              );
            },
            child: const Text('Copy link'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
        ],
      ),
    );
  }

  void _showUrlErrorDialog(String message) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Cannot open link'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }
  // ===========================================================================

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_savedJobs.isEmpty) {
      return const Center(child: Text('No saved jobs yet'));
    }
    return SmartRefresher(
      controller: _refreshController,
      onRefresh: _fetchSavedJobs,
      child: ListView.builder(
        itemCount: _savedJobs.length,
        itemBuilder: (ctx, i) {
          final job = _savedJobs[i];
          return Card(
            margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            child: ListTile(
              title: Text(job.title),
              subtitle: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('${job.company} • ${job.location ?? 'Unknown'}'),
                  const SizedBox(height: 4),
                  Text(job.description,
                      maxLines: 2, overflow: TextOverflow.ellipsis),
                ],
              ),
              trailing: IconButton(
                icon: const Icon(Icons.delete),
                onPressed: () => _unsaveJob(job.id),
              ),
              // Use improved URL handling
              onTap: () => _openJobUrl(job.url),
            ),
          );
        },
      ),
    );
  }
}