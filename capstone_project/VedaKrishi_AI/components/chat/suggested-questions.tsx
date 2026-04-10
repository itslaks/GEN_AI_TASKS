'use client'

import { Button } from '@/components/ui/button'
import { 
  Sprout, 
  Bug, 
  CloudRain, 
  Droplets, 
  Building2, 
  Leaf 
} from 'lucide-react'
import { LanguageCode } from './language-selector'

interface SuggestedQuestionsProps {
  onSelect: (question: string) => void
  language: LanguageCode
}

const QUESTIONS: Record<LanguageCode, Array<{ icon: typeof Sprout; question: string; label: string }>> = {
  en: [
    { icon: Sprout, question: 'What crops should I plant this Kharif season?', label: 'Crop Selection' },
    { icon: Bug, question: 'How do I control pests in my tomato crop organically?', label: 'Pest Control' },
    { icon: CloudRain, question: 'What is the weather forecast for farming this week?', label: 'Weather' },
    { icon: Droplets, question: 'How often should I irrigate my wheat field?', label: 'Irrigation' },
    { icon: Building2, question: 'How can I apply for PM-KISAN scheme?', label: 'Gov Schemes' },
    { icon: Leaf, question: 'How do I improve my soil health naturally?', label: 'Soil Health' },
  ],
  hi: [
    { icon: Sprout, question: 'इस खरीफ सीजन में मुझे कौन सी फसल लगानी चाहिए?', label: 'फसल चयन' },
    { icon: Bug, question: 'टमाटर की फसल में कीटों को जैविक तरीके से कैसे नियंत्रित करें?', label: 'कीट नियंत्रण' },
    { icon: CloudRain, question: 'इस सप्ताह खेती के लिए मौसम का पूर्वानुमान क्या है?', label: 'मौसम' },
    { icon: Droplets, question: 'गेहूं के खेत में कितनी बार सिंचाई करनी चाहिए?', label: 'सिंचाई' },
    { icon: Building2, question: 'पीएम-किसान योजना के लिए कैसे आवेदन करें?', label: 'सरकारी योजना' },
    { icon: Leaf, question: 'मिट्टी की सेहत को प्राकृतिक तरीके से कैसे सुधारें?', label: 'मिट्टी स्वास्थ्य' },
  ],
  ta: [
    { icon: Sprout, question: 'இந்த காரிப் பருவத்தில் எந்த பயிர்களை நடவு செய்ய வேண்டும்?', label: 'பயிர் தேர்வு' },
    { icon: Bug, question: 'தக்காளி பயிரில் இயற்கை முறையில் பூச்சிகளை கட்டுப்படுத்துவது எப்படி?', label: 'பூச்சி கட்டுப்பாடு' },
    { icon: CloudRain, question: 'இந்த வாரம் விவசாயத்திற்கான வானிலை முன்னறிவிப்பு என்ன?', label: 'வானிலை' },
    { icon: Droplets, question: 'கோதுமை வயலுக்கு எவ்வளவு அடிக்கடி நீர் பாய்ச்ச வேண்டும்?', label: 'நீர்ப்பாசனம்' },
    { icon: Building2, question: 'பிஎம்-கிசான் திட்டத்திற்கு எவ்வாறு விண்ணப்பிப்பது?', label: 'அரசு திட்டங்கள்' },
    { icon: Leaf, question: 'மண்ணின் ஆரோக்கியத்தை இயற்கையாக மேம்படுத்துவது எப்படி?', label: 'மண் ஆரோக்கியம்' },
  ],
  te: [
    { icon: Sprout, question: 'ఈ ఖరీఫ్ సీజన్‌లో ఏ పంటలు వేయాలి?', label: 'పంట ఎంపిక' },
    { icon: Bug, question: 'టమాటా పంటలో సేంద్రియ పద్ధతిలో చీడపీడలను ఎలా నియంత్రించాలి?', label: 'చీడపీడల నియంత్రణ' },
    { icon: CloudRain, question: 'ఈ వారం వ్యవసాయానికి వాతావరణ సూచన ఏమిటి?', label: 'వాతావరణం' },
    { icon: Droplets, question: 'గోధుమ పొలానికి ఎంత తరచుగా నీరు పెట్టాలి?', label: 'నీటిపారుదల' },
    { icon: Building2, question: 'PM-KISAN పథకానికి ఎలా దరఖాస్తు చేయాలి?', label: 'ప్రభుత్వ పథకాలు' },
    { icon: Leaf, question: 'మట్టి ఆరోగ్యాన్ని సహజంగా ఎలా మెరుగుపరచాలి?', label: 'మట్టి ఆరోగ్యం' },
  ],
  kn: [
    { icon: Sprout, question: 'ಈ ಖಾರಿಫ್ ಋತುವಿನಲ್ಲಿ ಯಾವ ಬೆಳೆಗಳನ್ನು ಬೆಳೆಯಬೇಕು?', label: 'ಬೆಳೆ ಆಯ್ಕೆ' },
    { icon: Bug, question: 'ಟೊಮೆಟೊ ಬೆಳೆಯಲ್ಲಿ ಸಾವಯವ ವಿಧಾನದಲ್ಲಿ ಕೀಟಗಳನ್ನು ಹೇಗೆ ನಿಯಂತ್ರಿಸುವುದು?', label: 'ಕೀಟ ನಿಯಂತ್ರಣ' },
    { icon: CloudRain, question: 'ಈ ವಾರ ಕೃಷಿಗೆ ಹವಾಮಾನ ಮುನ್ಸೂಚನೆ ಏನು?', label: 'ಹವಾಮಾನ' },
    { icon: Droplets, question: 'ಗೋಧಿ ಹೊಲಕ್ಕೆ ಎಷ್ಟು ಬಾರಿ ನೀರು ಹಾಕಬೇಕು?', label: 'ನೀರಾವರಿ' },
    { icon: Building2, question: 'PM-KISAN ಯೋಜನೆಗೆ ಹೇಗೆ ಅರ್ಜಿ ಸಲ್ಲಿಸುವುದು?', label: 'ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು' },
    { icon: Leaf, question: 'ಮಣ್ಣಿನ ಆರೋಗ್ಯವನ್ನು ನೈಸರ್ಗಿಕವಾಗಿ ಹೇಗೆ ಸುಧಾರಿಸುವುದು?', label: 'ಮಣ್ಣಿನ ಆರೋಗ್ಯ' },
  ],
  ml: [
    { icon: Sprout, question: 'ഈ ഖാരിഫ് സീസണിൽ ഏത് വിളകൾ നടണം?', label: 'വിള തിരഞ്ഞെടുപ്പ്' },
    { icon: Bug, question: 'തക്കാളി വിളയിൽ ജൈവ രീതിയിൽ കീടങ്ങളെ എങ്ങനെ നിയന്ത്രിക്കാം?', label: 'കീട നിയന്ത്രണം' },
    { icon: CloudRain, question: 'ഈ ആഴ്ച കൃഷിക്കുള്ള കാലാവസ്ഥ പ്രവചനം എന്താണ്?', label: 'കാലാവസ്ഥ' },
    { icon: Droplets, question: 'ഗോതമ്പ് പാടത്ത് എത്ര തവണ നനയ്ക്കണം?', label: 'ജലസേചനം' },
    { icon: Building2, question: 'PM-KISAN പദ്ധതിക്ക് എങ്ങനെ അപേക്ഷിക്കാം?', label: 'സർക്കാർ പദ്ധതികൾ' },
    { icon: Leaf, question: 'മണ്ണിന്റെ ആരോഗ്യം സ്വാഭാവികമായി എങ്ങനെ മെച്ചപ്പെടുത്താം?', label: 'മണ്ണ് ആരോഗ്യം' },
  ],
  bn: [
    { icon: Sprout, question: 'এই খারিফ মৌসুমে কোন ফসল চাষ করা উচিত?', label: 'ফসল নির্বাচন' },
    { icon: Bug, question: 'জৈব উপায়ে টমেটো ফসলে পোকামাকড় নিয়ন্ত্রণ কীভাবে করব?', label: 'পোকা নিয়ন্ত্রণ' },
    { icon: CloudRain, question: 'এই সপ্তাহে কৃষির জন্য আবহাওয়ার পূর্বাভাস কী?', label: 'আবহাওয়া' },
    { icon: Droplets, question: 'গমের জমিতে কতবার সেচ দেওয়া উচিত?', label: 'সেচ' },
    { icon: Building2, question: 'PM-KISAN প্রকল্পে কীভাবে আবেদন করব?', label: 'সরকারি প্রকল্প' },
    { icon: Leaf, question: 'প্রাকৃতিকভাবে মাটির স্বাস্থ্য কীভাবে উন্নত করব?', label: 'মাটি স্বাস্থ্য' },
  ],
  mr: [
    { icon: Sprout, question: 'या खरीप हंगामात कोणती पिके घ्यावीत?', label: 'पीक निवड' },
    { icon: Bug, question: 'टोमॅटो पिकातील किडींवर सेंद्रिय पद्धतीने नियंत्रण कसे ठेवावे?', label: 'कीड नियंत्रण' },
    { icon: CloudRain, question: 'या आठवड्यात शेतीसाठी हवामान अंदाज काय आहे?', label: 'हवामान' },
    { icon: Droplets, question: 'गव्हाच्या शेतात किती वेळा पाणी द्यावे?', label: 'सिंचन' },
    { icon: Building2, question: 'PM-KISAN योजनेसाठी कसे अर्ज करावे?', label: 'सरकारी योजना' },
    { icon: Leaf, question: 'मातीचे आरोग्य नैसर्गिकरित्या कसे सुधारावे?', label: 'माती आरोग्य' },
  ],
  gu: [
    { icon: Sprout, question: 'આ ખરીફ સીઝનમાં કઈ પાક વાવવી જોઈએ?', label: 'પાક પસંદગી' },
    { icon: Bug, question: 'ટામેટાના પાકમાં જૈવિક રીતે જીવાતોને કેવી રીતે નિયંત્રિત કરવી?', label: 'જીવાત નિયંત્રણ' },
    { icon: CloudRain, question: 'આ અઠવાડિયે ખેતી માટે હવામાનની આગાહી શું છે?', label: 'હવામાન' },
    { icon: Droplets, question: 'ઘઉંના ખેતરમાં કેટલી વાર પાણી આપવું જોઈએ?', label: 'સિંચાઈ' },
    { icon: Building2, question: 'PM-KISAN યોજના માટે કેવી રીતે અરજી કરવી?', label: 'સરકારી યોજનાઓ' },
    { icon: Leaf, question: 'જમીનની તંદુરસ્તી કુદરતી રીતે કેવી રીતે સુધારવી?', label: 'જમીન સ્વાસ્થ્ય' },
  ],
  pa: [
    { icon: Sprout, question: 'ਇਸ ਖਰੀਫ਼ ਸੀਜ਼ਨ ਵਿੱਚ ਕਿਹੜੀਆਂ ਫ਼ਸਲਾਂ ਬੀਜਣੀਆਂ ਚਾਹੀਦੀਆਂ ਹਨ?', label: 'ਫ਼ਸਲ ਚੋਣ' },
    { icon: Bug, question: 'ਟਮਾਟਰ ਦੀ ਫ਼ਸਲ ਵਿੱਚ ਜੈਵਿਕ ਢੰਗ ਨਾਲ ਕੀੜੇ ਕਿਵੇਂ ਕੰਟਰੋਲ ਕਰੀਏ?', label: 'ਕੀੜੇ ਕੰਟਰੋਲ' },
    { icon: CloudRain, question: 'ਇਸ ਹਫ਼ਤੇ ਖੇਤੀ ਲਈ ਮੌਸਮ ਦੀ ਭਵਿੱਖਬਾਣੀ ਕੀ ਹੈ?', label: 'ਮੌਸਮ' },
    { icon: Droplets, question: 'ਕਣਕ ਦੇ ਖੇਤ ਨੂੰ ਕਿੰਨੀ ਵਾਰ ਪਾਣੀ ਦੇਣਾ ਚਾਹੀਦਾ ਹੈ?', label: 'ਸਿੰਚਾਈ' },
    { icon: Building2, question: 'PM-KISAN ਸਕੀਮ ਲਈ ਕਿਵੇਂ ਅਪਲਾਈ ਕਰੀਏ?', label: 'ਸਰਕਾਰੀ ਸਕੀਮਾਂ' },
    { icon: Leaf, question: 'ਮਿੱਟੀ ਦੀ ਸਿਹਤ ਨੂੰ ਕੁਦਰਤੀ ਤੌਰ ਤੇ ਕਿਵੇਂ ਸੁਧਾਰੀਏ?', label: 'ਮਿੱਟੀ ਸਿਹਤ' },
  ],
  or: [
    { icon: Sprout, question: 'ଏହି ଖରିଫ୍ ଋତୁରେ କେଉଁ ଫସଲ ଚାଷ କରିବା ଉଚିତ?', label: 'ଫସଲ ଚୟନ' },
    { icon: Bug, question: 'ଟମାଟୋ ଫସଲରେ ଜୈବିକ ଉପାୟରେ କୀଟନାଶକ କିପରି ନିୟନ୍ତ୍ରଣ କରିବେ?', label: 'କୀଟ ନିୟନ୍ତ୍ରଣ' },
    { icon: CloudRain, question: 'ଏହି ସପ୍ତାହରେ ଚାଷ ପାଇଁ ପାଣିପାଗ ପୂର୍ବାନୁମାନ କଣ?', label: 'ପାଣିପାଗ' },
    { icon: Droplets, question: 'ଗହମ ଜମିରେ କେତେ ଥର ଜଳସେଚନ କରିବା ଉଚିତ?', label: 'ଜଳସେଚନ' },
    { icon: Building2, question: 'PM-KISAN ଯୋଜନା ପାଇଁ କିପରି ଆବେଦନ କରିବେ?', label: 'ସରକାରୀ ଯୋଜନା' },
    { icon: Leaf, question: 'ମାଟିର ସ୍ୱାସ୍ଥ୍ୟ ପ୍ରାକୃତିକ ଭାବେ କିପରି ଉନ୍ନତ କରିବେ?', label: 'ମାଟି ସ୍ୱାସ୍ଥ୍ୟ' },
  ],
  as: [
    { icon: Sprout, question: 'এই খাৰিফ ঋতুত কি শস্য খেতি কৰা উচিত?', label: 'শস্য নিৰ্বাচন' },
    { icon: Bug, question: 'বিলাহী শস্যত জৈৱিক পদ্ধতিৰে কীট-পতংগ কেনেকৈ নিয়ন্ত্ৰণ কৰিব?', label: 'কীট নিয়ন্ত্ৰণ' },
    { icon: CloudRain, question: 'এই সপ্তাহত কৃষিৰ বাবে বতৰৰ পূৰ্বানুমান কি?', label: 'বতৰ' },
    { icon: Droplets, question: 'ঘেঁহু পথাৰত কিমান সঘনাই জলসিঞ্চন কৰা উচিত?', label: 'জলসিঞ্চন' },
    { icon: Building2, question: 'PM-KISAN আঁচনিৰ বাবে কেনেকৈ আবেদন কৰিব?', label: 'চৰকাৰী আঁচনি' },
    { icon: Leaf, question: 'মাটিৰ স্বাস্থ্য প্ৰাকৃতিকভাৱে কেনেকৈ উন্নত কৰিব?', label: 'মাটি স্বাস্থ্য' },
  ],
}

export function SuggestedQuestions({ onSelect, language }: SuggestedQuestionsProps) {
  const questions = QUESTIONS[language] || QUESTIONS.en

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4">
      {questions.map((item, index) => {
        const Icon = item.icon
        return (
          <Button
            key={index}
            variant="outline"
            className="h-auto p-4 justify-start text-left flex-col items-start gap-2 bg-secondary/30 hover:bg-secondary/50 border-border"
            onClick={() => onSelect(item.question)}
          >
            <div className="flex items-center gap-2 text-primary">
              <Icon className="h-4 w-4" />
              <span className="text-xs font-medium uppercase tracking-wide">{item.label}</span>
            </div>
            <span className="text-sm text-foreground leading-relaxed">{item.question}</span>
          </Button>
        )
      })}
    </div>
  )
}
